import os, re, json, logging
from datetime import datetime, timezone, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (ApplicationBuilder, MessageHandler, CommandHandler,
                          ConversationHandler, CallbackQueryHandler,
                          filters, ContextTypes)
from supabase import create_client
import anthropic

TOKEN         = os.environ["TELEGRAM_TOKEN"]
SUPABASE_URL  = os.environ["SUPABASE_URL"]
SUPABASE_KEY  = os.environ["SUPABASE_KEY"]
ANTHROPIC_KEY = os.environ["ANTHROPIC_API_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
claude   = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
logging.basicConfig(level=logging.INFO)
ARG = timezone(timedelta(hours=-3))

(REGISTRO_NOMBRE,
 LOTE_CLIENTE, LOTE_CAMPO, LOTE_LOTE, LOTE_DESTINO,
 LOTE_CHASIS, LOTE_ACOPLADO, LOTE_CAPACIDAD,
 CAMION_CHASIS, CAMION_ACOPLADO, CAMION_CAPACIDAD) = range(11)

def ahora():
    return datetime.now(ARG)

def get_usuario(telegram_id: str):
    r = supabase.table("usuarios").select("*").eq("telegram_id", telegram_id).execute()
    return r.data[0] if r.data else None

def get_sesion(chat_id: str):
    r = supabase.table("sesion_activa").select(
        "*, clientes(nombre,apellido), campos(nombre), lotes(nombre), "
        "camiones(patente_chasis,patente_acoplado,capacidad_kg), "
        "silobolsas(numero)"
    ).eq("chat_id", chat_id).execute()
    return r.data[0] if r.data else None

def kg_acumulado_camion(camion_id: int, chat_id: str):
    r = supabase.table("descargas").select("kg").eq("camion_id", camion_id).eq("chat_id", chat_id).execute()
    return sum(float(x["kg"]) for x in r.data) if r.data else 0

def kg_acumulado_silo(silo_id: int):
    r = supabase.table("descargas").select("kg").eq("silobolsa_id", silo_id).execute()
    return sum(float(x["kg"]) for x in r.data) if r.data else 0

def barra(actual, total):
    if not total: return ""
    pct    = min(actual / total, 1.0)
    llenos = int(pct * 20)
    return "█" * llenos + "░" * (20 - llenos) + f" {pct*100:.0f}%"

def parsear_kg(texto: str):
    t = texto.upper()
    m = re.search(r'(\d[\d\.,]*)\s*(?:KGS?|KL|KILO|TON(?:ES|S)?)?', t)
    if not m: return None
    val = m.group(1).replace('.','').replace(',','.')
    kg  = float(val)
    if re.search(r'TON', t): kg *= 1000
    return kg if kg > 0 else None

def parsear_patentes(texto: str):
    t        = texto.upper()
    patentes = re.findall(r'\b([A-Z]{2,3}\s?\d{3}\s?[A-Z]{0,2})\b', t)
    return [re.sub(r'\s+', '', p) for p in patentes]

def armar_confirmacion(sesion, kg, acumulado_antes=None, destino_override=None):
    cliente_obj  = sesion.get("clientes") or {}
    cliente_str  = f"{cliente_obj.get('nombre','')} {cliente_obj.get('apellido','')}".strip() or "—"
    campo_str    = (sesion.get("campos")  or {}).get("nombre", "—")
    lote_str     = (sesion.get("lotes")   or {}).get("nombre", "—")
    destino      = destino_override or sesion.get("destino")
    chat_id      = sesion.get("chat_id", "")

    if destino == "camion":
        camion_obj   = sesion.get("camiones") or {}
        prev         = acumulado_antes if acumulado_antes is not None else kg_acumulado_camion(sesion["camion_id"], chat_id)
        acumulado    = prev + kg
        capacidad    = camion_obj.get("capacidad_kg")
        chasis_str   = camion_obj.get("patente_chasis",   "—")
        acoplado_str = camion_obj.get("patente_acoplado", "—")
        lineas = [
            f"✅ *{cliente_str} / {campo_str} / {lote_str}*",
            f"🚛 {chasis_str} — {acoplado_str}",
            f"Esta carga:  *{kg:,.0f} kg*",
            f"Acumulado:   *{acumulado:,.0f} kg*" + (f" / {capacidad:,.0f} kg" if capacidad else ""),
        ]
        if capacidad:
            faltan = max(capacidad - acumulado, 0)
            lineas.append(barra(acumulado, capacidad))
            aviso = " ⚠️ casi lleno" if acumulado / capacidad >= 0.85 else ""
            lineas.append(f"Faltan: *{faltan:,.0f} kg*{aviso}")
    else:
        silo_num  = (sesion.get("silobolsas") or {}).get("numero", "?")
        silo_id   = sesion.get("silo_id")
        prev      = acumulado_antes if acumulado_antes is not None else (kg_acumulado_silo(silo_id) if silo_id else 0)
        acumulado = prev + kg
        lineas = [
            f"✅ *{cliente_str} / {campo_str} / {lote_str}*",
            f"🌾 Silobolsa #{silo_num}",
            f"Esta carga:  *{kg:,.0f} kg*",
            f"Acumulado:   *{acumulado:,.0f} kg*",
        ]
    return "\n".join(lineas)

def guardar_descarga(sesion, kg, usuario, ts):
    destino = sesion.get("destino")
    data = {
        "kg":           kg,
        "destino":      destino,
        "camion_id":    sesion.get("camion_id") if destino == "camion" else None,
        "silobolsa_id": sesion.get("silo_id")   if destino == "silo"   else None,
        "lote_id":      sesion.get("lote_id"),
        "campo_id":     sesion.get("campo_id"),
        "cliente_id":   sesion.get("cliente_id"),
        "tolva":        sesion.get("chat_id"),
        "operario_id":  usuario["id"] if usuario else None,
        "chat_id":      sesion["chat_id"],
        "created_at":   ts.isoformat(),
    }
    supabase.table("descargas").insert(data).execute()

# ── /start ───────────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid     = str(update.effective_user.id)
    usuario = get_usuario(uid)
    if usuario:
        await update.message.reply_text(
            f"Hola {usuario['nombre']}! Ya estás registrado como *{usuario['rol']}*.\n"
            "Usá /ayuda para ver los comandos.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    teclado = InlineKeyboardMarkup([
        [InlineKeyboardButton("👷 Operario de tolva",      callback_data="rol_operario")],
        [InlineKeyboardButton("👤 Cliente / dueño granos", callback_data="rol_cliente")],
        [InlineKeyboardButton("⚙️ Encargado del equipo",   callback_data="rol_encargado")],
    ])
    await update.message.reply_text("Hola! Bienvenido al bot de tolvas.\n\n¿Quién sos?", reply_markup=teclado)
    return REGISTRO_NOMBRE

async def elegir_rol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    rol   = query.data.replace("rol_", "")
    context.user_data["rol"] = rol
    roles = {"operario": "Operario", "cliente": "Cliente", "encargado": "Encargado"}
    await query.edit_message_text(
        f"Elegiste: *{roles[rol]}*\n\n¿Cuál es tu nombre y apellido?",
        parse_mode="Markdown"
    )
    return REGISTRO_NOMBRE

async def recibir_nombre_registro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nombre = update.message.text.strip()
    rol    = context.user_data.get("rol", "operario")
    uid    = str(update.effective_user.id)
    supabase.table("usuarios").insert({
        "telegram_id": uid, "nombre": nombre, "rol": rol, "activo": True
    }).execute()
    msgs = {
        "operario":  "Cuando quieras cargar una descarga mandame la patente del chasis, acoplado y los kg.\nEj: `AB123CD XY456ZW 5400kg`",
        "cliente":   "Podés pedirme el resumen de tus granos cuando quieras con /resumen.",
        "encargado": "Tenés acceso completo. Usá /ayuda para ver todo."
    }
    await update.message.reply_text(
        f"✅ Bienvenido *{nombre}*! Quedaste registrado como *{rol}*.\n\n{msgs[rol]}",
        parse_mode="Markdown"
    )
    return ConversationHandler.END

# ── /ayuda ───────────────────────────────────────────────────
async def cmd_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid     = str(update.effective_user.id)
    usuario = get_usuario(uid)
    if not usuario:
        await update.message.reply_text("Primero registrate con /start.")
        return
    rol = usuario["rol"]
    if rol == "operario":
        texto = (
            "🌾 *Comandos operario*\n\n"
            "*Registrar descarga a camión:*\n"
            "`AB123CD XY456ZW 5400kg`\n\n"
            "*Registrar descarga a silobolsa:*\n"
            "`5400kg`\n\n"
            "/nuevolote — cambiar cliente, campo y lote\n"
            "/nuevocamion — cambiar camión activo\n"
            "/nuevosilo — abrir silobolsa nuevo\n"
            "/camion ABC123 — ver estado de un camión\n"
            "/resumen — total de hoy"
        )
    elif rol == "cliente":
        texto = (
            "📊 *Comandos cliente*\n\n"
            "/resumen — tus kg de hoy\n"
            "/resumen semana — últimos 7 días\n"
            "/resumen mes — mes actual"
        )
    else:
        texto = (
            "⚙️ *Comandos encargado*\n\n"
            "/resumen — todo el día\n"
            "/resumen semana — últimos 7 días\n"
            "/camion ABC123 — estado de un camión\n"
            "/nuevolote — cambiar sesión activa"
        )
    await update.message.reply_text(texto, parse_mode="Markdown")

# ── /nuevolote ───────────────────────────────────────────────
async def cmd_nuevolote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid     = str(update.effective_user.id)
    usuario = get_usuario(uid)
    if not usuario or usuario["rol"] not in ("operario", "encargado"):
        await update.message.reply_text("Solo operarios y encargados pueden hacer esto.")
        return ConversationHandler.END
    context.user_data.clear()
    await update.message.reply_text("¿Para qué cliente es esta cosecha? (nombre o apellido)")
    return LOTE_CLIENTE

async def lote_recibir_cliente(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    r = supabase.table("clientes").select("*").ilike("apellido", f"%{texto}%").execute()
    if not r.data:
        r = supabase.table("clientes").select("*").ilike("nombre", f"%{texto}%").execute()
    if not r.data:
        partes = texto.split()
        nuevo  = supabase.table("clientes").insert({
            "nombre":   partes[0],
            "apellido": " ".join(partes[1:]) if len(partes) > 1 else ""
        }).execute()
        context.user_data["cliente_id"]  = nuevo.data[0]["id"]
        context.user_data["cliente_str"] = texto
        await update.message.reply_text(f"Cliente *{texto}* creado.\n\n¿En qué campo?", parse_mode="Markdown")
    elif len(r.data) == 1:
        context.user_data["cliente_id"]  = r.data[0]["id"]
        context.user_data["cliente_str"] = f"{r.data[0]['nombre']} {r.data[0]['apellido']}"
        await update.message.reply_text(
            f"✅ *{context.user_data['cliente_str']}*\n\n¿En qué campo?", parse_mode="Markdown"
        )
    else:
        teclado = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{x['nombre']} {x['apellido']}", callback_data=f"cli_{x['id']}")]
            for x in r.data
        ])
        await update.message.reply_text("Encontré varios, ¿cuál es?", reply_markup=teclado)
    return LOTE_CAMPO

async def lote_elegir_cliente(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cid   = int(query.data.replace("cli_", ""))
    r     = supabase.table("clientes").select("*").eq("id", cid).execute()
    c     = r.data[0]
    context.user_data["cliente_id"]  = cid
    context.user_data["cliente_str"] = f"{c['nombre']} {c['apellido']}"
    await query.edit_message_text(
        f"✅ *{context.user_data['cliente_str']}*\n\n¿En qué campo?", parse_mode="Markdown"
    )
    return LOTE_CAMPO

async def lote_recibir_campo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto      = update.message.text.strip()
    cliente_id = context.user_data["cliente_id"]
    r = supabase.table("campos").select("*").eq("cliente_id", cliente_id).ilike("nombre", f"%{texto}%").execute()
    if r.data:
        context.user_data["campo_id"] = r.data[0]["id"]
        await update.message.reply_text(
            f"✅ Campo *{r.data[0]['nombre']}*\n\n¿En qué lote?", parse_mode="Markdown"
        )
    else:
        nuevo = supabase.table("campos").insert({"nombre": texto, "cliente_id": cliente_id}).execute()
        context.user_data["campo_id"] = nuevo.data[0]["id"]
        await update.message.reply_text(f"Campo *{texto}* creado.\n\n¿En qué lote?", parse_mode="Markdown")
    return LOTE_LOTE

async def lote_recibir_lote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto    = update.message.text.strip()
    campo_id = context.user_data["campo_id"]
    r = supabase.table("lotes").select("*").eq("campo_id", campo_id).ilike("nombre", f"%{texto}%").execute()
    if r.data:
        context.user_data["lote_id"] = r.data[0]["id"]
    else:
        nuevo = supabase.table("lotes").insert({"nombre": texto, "campo_id": campo_id}).execute()
        context.user_data["lote_id"] = nuevo.data[0]["id"]

    teclado = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚛 Camión",    callback_data="dest_camion")],
        [InlineKeyboardButton("🌾 Silobolsa", callback_data="dest_silo")],
    ])
    await update.message.reply_text(
        f"✅ Lote *{texto}*\n\n¿Las descargas van a camión o silobolsa?",
        parse_mode="Markdown", reply_markup=teclado
    )
    return LOTE_DESTINO

async def lote_elegir_destino(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    chat_id = str(update.effective_chat.id)

    supabase.table("sesion_activa").upsert({
        "chat_id":     chat_id,
        "cliente_id":  context.user_data["cliente_id"],
        "campo_id":    context.user_data["campo_id"],
        "lote_id":     context.user_data["lote_id"],
        "destino":     None, "camion_id": None, "silo_id": None,
        "iniciada_at": ahora().isoformat()
    }).execute()

    if query.data == "dest_silo":
        lote_id = context.user_data["lote_id"]
        r       = supabase.table("silobolsas").select("numero").eq("lote_id", lote_id).order("numero", desc=True).execute()
        numero  = (r.data[0]["numero"] + 1) if r.data else 1
        nuevo   = supabase.table("silobolsas").insert({"numero": numero, "lote_id": lote_id}).execute()
        supabase.table("sesion_activa").update({
            "destino": "silo", "silo_id": nuevo.data[0]["id"]
        }).eq("chat_id", chat_id).execute()
        await query.edit_message_text(
            f"✅ Sesión iniciada\n🌾 Silobolsa #{numero} abierto.\n\nMandá las descargas.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    await query.edit_message_text("¿Patente del *chasis*? (ej: AB123CD)", parse_mode="Markdown")
    return LOTE_CHASIS

async def lote_recibir_chasis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["patente_chasis"] = re.sub(r'\s+', '', update.message.text.upper().strip())
    await update.message.reply_text("¿Patente del *acoplado*?", parse_mode="Markdown")
    return LOTE_ACOPLADO

async def lote_recibir_acoplado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["patente_acoplado"] = re.sub(r'\s+', '', update.message.text.upper().strip())
    await update.message.reply_text(
        "¿Capacidad del camión en kg? (ej: `30000`)\nSi no sabés escribí *0*",
        parse_mode="Markdown"
    )
    return LOTE_CAPACIDAD

async def lote_recibir_capacidad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id  = str(update.effective_chat.id)
    try:
        cap = float(update.message.text.strip().replace('.','').replace(',','.'))
    except ValueError:
        cap = 0
    chasis   = context.user_data["patente_chasis"]
    acoplado = context.user_data["patente_acoplado"]
    r = supabase.table("camiones").select("*").eq("patente_chasis", chasis).eq("patente_acoplado", acoplado).execute()
    if r.data:
        camion_id = r.data[0]["id"]
        if cap > 0:
            supabase.table("camiones").update({"capacidad_kg": cap}).eq("id", camion_id).execute()
    else:
        nuevo     = supabase.table("camiones").insert({
            "patente_chasis": chasis, "patente_acoplado": acoplado,
            "capacidad_kg": cap if cap > 0 else None
        }).execute()
        camion_id = nuevo.data[0]["id"]
    supabase.table("sesion_activa").update({
        "destino": "camion", "camion_id": camion_id
    }).eq("chat_id", chat_id).execute()
    await update.message.reply_text(
        f"✅ Sesión iniciada\n🚛 Camión *{chasis} / {acoplado}* listo.\n\nMandá las descargas.",
        parse_mode="Markdown"
    )
    return ConversationHandler.END

# ── /nuevocamion ─────────────────────────────────────────────
async def cmd_nuevocamion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid     = str(update.effective_user.id)
    usuario = get_usuario(uid)
    if not usuario or usuario["rol"] not in ("operario", "encargado"):
        await update.message.reply_text("Solo operarios y encargados pueden hacer esto.")
        return ConversationHandler.END
    context.user_data.clear()
    await update.message.reply_text("¿Patente del *chasis*?", parse_mode="Markdown")
    return CAMION_CHASIS

async def camion_recibir_chasis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["patente_chasis"] = re.sub(r'\s+', '', update.message.text.upper().strip())
    await update.message.reply_text("¿Patente del *acoplado*?", parse_mode="Markdown")
    return CAMION_ACOPLADO

async def camion_recibir_acoplado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["patente_acoplado"] = re.sub(r'\s+', '', update.message.text.upper().strip())
    await update.message.reply_text(
        "¿Capacidad en kg? (ej: `30000`) — Si no sabés escribí *0*",
        parse_mode="Markdown"
    )
    return CAMION_CAPACIDAD

async def camion_recibir_capacidad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id  = str(update.effective_chat.id)
    try:
        cap = float(update.message.text.strip().replace('.','').replace(',','.'))
    except ValueError:
        cap = 0
    chasis   = context.user_data["patente_chasis"]
    acoplado = context.user_data["patente_acoplado"]
    r = supabase.table("camiones").select("*").eq("patente_chasis", chasis).eq("patente_acoplado", acoplado).execute()
    if r.data:
        camion_id = r.data[0]["id"]
        if cap > 0:
            supabase.table("camiones").update({"capacidad_kg": cap}).eq("id", camion_id).execute()
    else:
        nuevo     = supabase.table("camiones").insert({
            "patente_chasis": chasis, "patente_acoplado": acoplado,
            "capacidad_kg": cap if cap > 0 else None
        }).execute()
        camion_id = nuevo.data[0]["id"]
    supabase.table("sesion_activa").update({
        "destino": "camion", "camion_id": camion_id, "silo_id": None
    }).eq("chat_id", chat_id).execute()
    await update.message.reply_text(
        f"🚛 Camión *{chasis} / {acoplado}* activo. Mandá las descargas.",
        parse_mode="Markdown"
    )
    return ConversationHandler.END

# ── /nuevosilo ───────────────────────────────────────────────
async def cmd_nuevosilo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    sesion  = get_sesion(chat_id)
    if not sesion or not sesion.get("lote_id"):
        await update.message.reply_text("Primero iniciá una sesión con /nuevolote.")
        return
    lote_id = sesion["lote_id"]
    r       = supabase.table("silobolsas").select("numero").eq("lote_id", lote_id).order("numero", desc=True).execute()
    numero  = (r.data[0]["numero"] + 1) if r.data else 1
    nuevo   = supabase.table("silobolsas").insert({"numero": numero, "lote_id": lote_id}).execute()
    supabase.table("sesion_activa").update({
        "destino": "silo", "silo_id": nuevo.data[0]["id"], "camion_id": None
    }).eq("chat_id", chat_id).execute()
    await update.message.reply_text(f"🌾 Silobolsa #{numero} abierto. Mandá las descargas.")

# ── /camion ──────────────────────────────────────────────────
async def cmd_camion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usá: /camion PATENTE — ej: /camion AB123CD")
        return
    patente = context.args[0].upper()
    r = supabase.table("camiones").select("*").eq("patente_chasis", patente).execute()
    if not r.data:
        r = supabase.table("camiones").select("*").eq("patente_acoplado", patente).execute()
    if not r.data:
        await update.message.reply_text(f"No encontré el camión {patente}.")
        return
    camion    = r.data[0]
    chat_id   = str(update.effective_chat.id)
    acumulado = kg_acumulado_camion(camion["id"], chat_id)
    capacidad = camion.get("capacidad_kg")
    lineas    = [
        f"🚛 *{camion['patente_chasis']} / {camion['patente_acoplado']}*",
        f"Acumulado: *{acumulado:,.0f} kg*"
    ]
    if capacidad:
        faltan = max(capacidad - acumulado, 0)
        lineas.append(barra(acumulado, capacidad))
        lineas.append(f"Capacidad: {capacidad:,.0f} kg — Faltan: {faltan:,.0f} kg")
    await update.message.reply_text("\n".join(lineas), parse_mode="Markdown")

# ── /resumen ─────────────────────────────────────────────────
async def cmd_resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid     = str(update.effective_user.id)
    usuario = get_usuario(uid)
    if not usuario:
        await update.message.reply_text("Primero registrate con /start.")
        return
    args     = " ".join(context.args).lower() if context.args else ""
    ahora_ts = ahora()
    if "mes" in args:
        desde  = ahora_ts.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        titulo = f"Mes {ahora_ts.strftime('%B %Y')}"
    elif "semana" in args:
        desde  = ahora_ts - timedelta(days=7)
        titulo = "Últimos 7 días"
    else:
        desde  = ahora_ts.replace(hour=0, minute=0, second=0, microsecond=0)
        titulo = f"Hoy {ahora_ts.strftime('%d/%m/%Y')}"

    q = (supabase.table("descargas")
         .select("kg, destino, camion_id, silobolsa_id, cliente_id, clientes(nombre,apellido)")
         .gte("created_at", desde.isoformat()))
    if usuario["rol"] == "cliente":
        q = q.eq("cliente_id", usuario.get("cliente_id"))
    res = q.order("created_at", desc=True).execute()

    if not res.data:
        await update.message.reply_text(f"Sin registros para {titulo}.")
        return

    total_kg     = sum(float(r["kg"]) for r in res.data)
    camiones_set = {r["camion_id"]    for r in res.data if r["camion_id"]}
    silos_set    = {r["silobolsa_id"] for r in res.data if r["silobolsa_id"]}
    lineas = [
        f"📊 *{titulo}*\n",
        f"Total: *{total_kg:,.0f} kg*",
        f"Camiones: {len(camiones_set)}  |  Silobolsas: {len(silos_set)}",
        f"Descargas: {len(res.data)}\n"
    ]
    if usuario["rol"] == "encargado":
        clientes = {}
        for r in res.data:
            c      = r.get("clientes")
            nombre = f"{c['nombre']} {c['apellido']}" if c else "Sin cliente"
            clientes[nombre] = clientes.get(nombre, 0) + float(r["kg"])
        for nombre, kg in sorted(clientes.items()):
            lineas.append(f"👤 *{nombre}*: {kg:,.0f} kg")
    await update.message.reply_text("\n".join(lineas), parse_mode="Markdown")

# ── Claude para mensajes ambiguos ────────────────────────────
def consultar_claude_libre(mensaje: str, sesion, usuario) -> str:
    sesion_str = "Sin sesión activa."
    if sesion and sesion.get("lote_id"):
        cliente_obj = sesion.get("clientes") or {}
        sesion_str  = (
            f"Cliente: {cliente_obj.get('nombre','')} {cliente_obj.get('apellido','')}, "
            f"Campo: {(sesion.get('campos') or {}).get('nombre','')}, "
            f"Lote: {(sesion.get('lotes') or {}).get('nombre','')}, "
            f"Destino: {sesion.get('destino') or 'no definido'}"
        )
    system = (
        "Sos el asistente de un sistema de tolvas agrícolas argentino. "
        "Respondé siempre en español rioplatense, breve y directo. "
        f"Sesión activa: {sesion_str}. "
        f"Usuario: {usuario['nombre']} ({usuario['rol']}). "
        "Si el mensaje es un saludo o consulta general, respondé amigablemente. "
        "Si parece que quiere registrar una descarga pero le falta info, "
        "decile exactamente qué formato usar: patente chasis, patente acoplado y kg. "
        "Nunca inventes datos ni hagas preguntas de más."
    )
    try:
        resp = claude.messages.create(
            model="claude-haiku-4-5",
            max_tokens=256,
            system=system,
            messages=[{"role": "user", "content": mensaje}]
        )
        return resp.content[0].text.strip()
    except Exception as e:
        logging.error(f"Error Claude: {e}")
        return "No entendí el mensaje. Usá el formato: `AB123CD XY456ZW 5400kg`"

# ── Handler principal ────────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid     = str(update.effective_user.id)
    usuario = get_usuario(uid)
    msg     = update.message
    texto   = msg.text or ""
    chat_id = str(update.effective_chat.id)
    ts      = msg.date.astimezone(ARG)

    if not usuario:
        await msg.reply_text("No te conozco. Escribí /start para registrarte.")
        return

    if usuario["rol"] == "cliente":
        await msg.reply_text("Usá /resumen para consultar tus datos.")
        return

    sesion = get_sesion(chat_id)

    if not sesion or not sesion.get("lote_id"):
        await msg.reply_text(
            "No hay sesión activa.\nUsá /nuevolote para indicar cliente, campo y lote."
        )
        return

    patentes = parsear_patentes(texto)
    kg       = parsear_kg(texto)

    if kg and len(patentes) >= 2:
        chasis, acoplado = patentes[0], patentes[1]
        r = supabase.table("camiones").select("*").eq("patente_chasis", chasis).eq("patente_acoplado", acoplado).execute()
        if r.data:
            camion_id = r.data[0]["id"]
        else:
            nuevo     = supabase.table("camiones").insert({
                "patente_chasis": chasis, "patente_acoplado": acoplado
            }).execute()
            camion_id = nuevo.data[0]["id"]
        supabase.table("sesion_activa").update({
            "destino": "camion", "camion_id": camion_id, "silo_id": None
        }).eq("chat_id", chat_id).execute()
        sesion            = get_sesion(chat_id)
        acumulado_antes   = kg_acumulado_camion(camion_id, chat_id)
        guardar_descarga(sesion, kg, usuario, ts)
        await msg.reply_text(armar_confirmacion(sesion, kg, acumulado_antes), parse_mode="Markdown")
        return

    if kg and sesion.get("destino"):
        destino = sesion.get("destino")
        if destino == "camion":
            acumulado_antes = kg_acumulado_camion(sesion["camion_id"], chat_id)
        else:
            acumulado_antes = kg_acumulado_silo(sesion["silo_id"]) if sesion.get("silo_id") else 0
        guardar_descarga(sesion, kg, usuario, ts)
        await msg.reply_text(armar_confirmacion(sesion, kg, acumulado_antes), parse_mode="Markdown")
        return

    if kg and not sesion.get("destino"):
        teclado = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚛 Camión",    callback_data=f"dest_kg_{kg}_camion")],
            [InlineKeyboardButton("🌾 Silobolsa", callback_data=f"dest_kg_{kg}_silo")],
        ])
        await msg.reply_text(
            f"Son *{kg:,.0f} kg* — ¿a dónde van?",
            parse_mode="Markdown", reply_markup=teclado
        )
        return

    respuesta = consultar_claude_libre(texto, sesion, usuario)
    await msg.reply_text(respuesta, parse_mode="Markdown")

async def destino_kg_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    chat_id = str(update.effective_chat.id)
    partes  = query.data.split("_")
    kg      = float(partes[2])
    destino = partes[3]
    sesion  = get_sesion(chat_id)
    uid     = str(update.effective_user.id)
    usuario = get_usuario(uid)
    ts      = update.callback_query.message.date.astimezone(ARG)

    if destino == "silo":
        if not sesion.get("silo_id"):
            lote_id = sesion["lote_id"]
            r       = supabase.table("silobolsas").select("numero").eq("lote_id", lote_id).order("numero", desc=True).execute()
            numero  = (r.data[0]["numero"] + 1) if r.data else 1
            nuevo   = supabase.table("silobolsas").insert({"numero": numero, "lote_id": lote_id}).execute()
            supabase.table("sesion_activa").update({
                "destino": "silo", "silo_id": nuevo.data[0]["id"], "camion_id": None
            }).eq("chat_id", chat_id).execute()
        else:
            supabase.table("sesion_activa").update({"destino": "silo"}).eq("chat_id", chat_id).execute()
        acumulado_antes = kg_acumulado_silo(sesion.get("silo_id") or 0)
    else:
        supabase.table("sesion_activa").update({"destino": "camion"}).eq("chat_id", chat_id).execute()
        acumulado_antes = kg_acumulado_camion(sesion["camion_id"], chat_id) if sesion.get("camion_id") else 0

    sesion = get_sesion(chat_id)
    guardar_descarga(sesion, kg, usuario, ts)
    await query.edit_message_text(armar_confirmacion(sesion, kg, acumulado_antes), parse_mode="Markdown")

# ── Main ─────────────────────────────────────────────────────
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    registro_conv = ConversationHandler(
        entry_points=[CommandHandler("start", cmd_start)],
        states={
            REGISTRO_NOMBRE: [
                CallbackQueryHandler(elegir_rol, pattern="^rol_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_nombre_registro),
            ],
        },
        fallbacks=[]
    )

    lote_conv = ConversationHandler(
        entry_points=[CommandHandler("nuevolote", cmd_nuevolote)],
        states={
            LOTE_CLIENTE:   [CallbackQueryHandler(lote_elegir_cliente, pattern="^cli_"),
                             MessageHandler(filters.TEXT & ~filters.COMMAND, lote_recibir_cliente)],
            LOTE_CAMPO:     [MessageHandler(filters.TEXT & ~filters.COMMAND, lote_recibir_campo)],
            LOTE_LOTE:      [MessageHandler(filters.TEXT & ~filters.COMMAND, lote_recibir_lote)],
            LOTE_DESTINO:   [CallbackQueryHandler(lote_elegir_destino, pattern="^dest_")],
            LOTE_CHASIS:    [MessageHandler(filters.TEXT & ~filters.COMMAND, lote_recibir_chasis)],
            LOTE_ACOPLADO:  [MessageHandler(filters.TEXT & ~filters.COMMAND, lote_recibir_acoplado)],
            LOTE_CAPACIDAD: [MessageHandler(filters.TEXT & ~filters.COMMAND, lote_recibir_capacidad)],
        },
        fallbacks=[]
    )

    camion_conv = ConversationHandler(
        entry_points=[CommandHandler("nuevocamion", cmd_nuevocamion)],
        states={
            CAMION_CHASIS:    [MessageHandler(filters.TEXT & ~filters.COMMAND, camion_recibir_chasis)],
            CAMION_ACOPLADO:  [MessageHandler(filters.TEXT & ~filters.COMMAND, camion_recibir_acoplado)],
            CAMION_CAPACIDAD: [MessageHandler(filters.TEXT & ~filters.COMMAND, camion_recibir_capacidad)],
        },
        fallbacks=[]
    )

    app.add_handler(registro_conv)
    app.add_handler(lote_conv)
    app.add_handler(camion_conv)
    app.add_handler(CallbackQueryHandler(destino_kg_callback, pattern="^dest_kg_"))
    app.add_handler(CommandHandler("ayuda",      cmd_ayuda))
    app.add_handler(CommandHandler("resumen",    cmd_resumen))
    app.add_handler(CommandHandler("nuevosilo",  cmd_nuevosilo))
    app.add_handler(CommandHandler("camion",     cmd_camion))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot corriendo...")
    app.run_polling()
