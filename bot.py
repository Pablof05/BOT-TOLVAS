import os, re, logging
from datetime import datetime, timezone, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
from supabase import create_client

TOKEN        = os.environ["TELEGRAM_TOKEN"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
logging.basicConfig(level=logging.INFO)
ARG = timezone(timedelta(hours=-3))

def parsear(texto: str):
    t = texto.upper().strip()
    m_pat = re.search(r'\b([A-Z]{2,3}\s?\d{3}\s?[A-Z]{0,2})\b', t)
    m_kg  = re.search(r'(\d[\d\.,]*)\s*KG[S]?', t)
    if m_pat and m_kg:
        patente = re.sub(r'\s+', '', m_pat.group(1))
        kg_str  = m_kg.group(1).replace('.', '').replace(',', '.')
        return patente, float(kg_str)
    return None

def ts_original(update: Update):
    return update.message.date.astimezone(ARG)

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌾 *Bot de Tolvas*\n\n"
        "Para registrar una descarga mandá:\n"
        "`PATENTE kg` — ej: `AB123CD 5400kg`\n\n"
        "Comandos:\n"
        "/resumen — total de hoy\n"
        "/resumen semana — últimos 7 días\n"
        "/resumen mes — mes actual",
        parse_mode="Markdown"
    )

async def cmd_resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args  = " ".join(context.args).lower() if context.args else ""
    ahora = datetime.now(ARG)

    if "mes" in args:
        desde = ahora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        titulo = f"Mes {ahora.strftime('%B %Y')}"
    elif "semana" in args:
        desde = ahora - timedelta(days=7)
        titulo = "Últimos 7 días"
    else:
        desde = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
        titulo = f"Hoy {ahora.strftime('%d/%m/%Y')}"

    res = (supabase.table("descargas")
           .select("kg, tolva, patente, created_at")
           .gte("created_at", desde.isoformat())
           .order("created_at", desc=True)
           .execute())

    if not res.data:
        await update.message.reply_text(f"Sin registros para {titulo}.")
        return

    tolvas = {}
    for r in res.data:
        t = r["tolva"] or "Sin tolva"
        tolvas.setdefault(t, {"kg": 0, "camiones": set()})
        tolvas[t]["kg"] += float(r["kg"])
        tolvas[t]["camiones"].add(r["patente"])

    total_kg       = sum(v["kg"] for v in tolvas.values())
    total_camiones = sum(len(v["camiones"]) for v in tolvas.values())

    lineas = [f"📊 *{titulo}*\n"]
    for nombre, v in sorted(tolvas.items()):
        lineas.append(
            f"🌾 *{nombre}*\n"
            f"   {v['kg']:,.0f} kg — {len(v['camiones'])} camiones\n"
        )
    lineas.append(f"\n*Total: {total_kg:,.0f} kg — {total_camiones} camiones*")

    await update.message.reply_text("\n".join(lineas), parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg   = update.message
    user  = msg.from_user
    chat  = msg.chat
    texto = msg.text or ""

    tolva = chat.title if chat.type in ("group", "supergroup") else "directa"
    resultado = parsear(texto)

    if resultado is None:
        if re.search(r'\d{3,}', texto):
            await msg.reply_text(
                "⚠️ No entendí el formato.\n"
                "Mandá: `PATENTE kg` — ej: `AB123CD 5400kg`",
                parse_mode="Markdown"
            )
        return

    patente, kg = resultado
    ts = ts_original(update)

    data = {
        "patente":         patente,
        "kg":              kg,
        "tolva":           tolva,
        "operario_id":     str(user.id),
        "operario_nombre": user.full_name,
        "chat_id":         str(chat.id),
        "created_at":      ts.isoformat(),
    }

    resp = supabase.table("descargas").insert(data).execute()

    if resp.data:
        await msg.reply_text(
            f"✅ *Registrado*\n"
            f"Patente: `{patente}`\n"
            f"Kg: `{kg:,.0f}`\n"
            f"Tolva: {tolva}\n"
            f"Hora: {ts.strftime('%H:%M %d/%m')}",
            parse_mode="Markdown"
        )
    else:
        await msg.reply_text("❌ Error al guardar. Intentá de nuevo.")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("resumen", cmd_resumen))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Bot corriendo...")
    app.run_polling()
