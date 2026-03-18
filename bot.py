import os, re, logging
from datetime import datetime, timezone, timedelta
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (ApplicationBuilder, MessageHandler, CommandHandler,
                          ConversationHandler, filters, ContextTypes)
from supabase import create_client

TOKEN        = os.environ["TELEGRAM_TOKEN"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
logging.basicConfig(level=logging.INFO)
ARG = timezone(timedelta(hours=-3))

# ── Estados del ConversationHandler ─────────────────────────
(ROL, NOMBRE,
 CLIENTE, CAMPO, LOTE,
 DESTINO, PATENTE_CHASIS, PATENTE_ACOPLADO, CAPACIDAD,
 NUEVO_CAMION_CHASIS, NUEVO_CAMION_ACOPLADO, NUEVO_CAMION_CAP) = range(12)

# ── Helpers ──────────────────────────────────────────────────
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

def barra(actual, total):
    if not total:
        return ""
    pct = min(actual / total, 1.0)
    llenos = int(pct * 20)
    return "█" * llenos + "░" * (20 - llenos) + f" {pct*100:.0f}%"

def kg_acumulado_camion(camion_id: int, sesion_chat_id: str):
    r = supabase.table("descargas").select("kg").eq("camion_id", camion_id).eq("chat_id", sesion_chat_id).execute()
    return sum(float(x["kg"]) for x in r.data) if r.data else 0

def kg_acumulado_silo(silo_id: int):
    r = supabase.table("descargas").select("kg").eq("silobolsa_id", silo_id).execute()
    return sum(float(x["kg"]) for x in r.data) if r.data else 0

def parsear_descarga(texto: str):
    t = texto.upper().strip()
    m_kg = re.search(r'(\d[\d\.,]*)\s*KG[S]?', t)
    if not m_kg:
        return None
    kg_str = m_kg.group(1).replace('.', '').replace(',', '.')
    kg = float(kg_str)
    patentes = re.findall(r'\b([A-Z]{2,3}\s?\d{3}\s?[A-Z]{0,2})\b', t)
    patentes = [re.sub(r'\s+', '', p) for p in patentes]
    return kg, patentes

# ── /start — registro de usuario nuevo ──────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    usuario = get_usuario(uid)
    if usuario:
        await update.message.reply_text(
            f"Hola {usuario['nombre']}, ya estás registrado como *{usuario['rol']}*.\n"
            "Mandá una descarga o usá /ayuda.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    teclado = [["Operario", "Cliente", "Encargado"]]
    await update.message.reply_text(
        "Hola, no te conozco todavía. ¿Quién sos?",
        reply_markup=ReplyKeyboardMarkup(teclado, one_time_keyboard=True, resize_keyboard=True)
    )
    return ROL

async def recibir_rol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.lower().strip()
    if texto not in ["operario", "cliente", "encargado"]:
        await update.message.reply_text("Elegí una opción del teclado.")
        return ROL
    context.user_data["rol"] = texto
    await update.message.reply_text(
        "¿Cuál es tu nombre y apellido?",
        reply_markup=ReplyKeyboardRemove()
    )
    return NOMBRE

async def recibir_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nombre = update.message.text.strip()
    rol    = context.user_data["rol"]
    uid    = str(update.effective_user.id)

    supabase.table("usuarios").insert({
        "telegram_id": uid,
        "nombre":      nombre,
        "rol":         rol,
        "activo":      True
    }).execute()

    await update.message.reply_text(
        f"✅ Registrado como *{rol}*. Bienvenido {nombre}!\n\n"
        + ("Mandá una descarga cuando quieras. Usá /ayuda si tenés dudas." if rol == "operario"
           else "Usá /resumen para consultar tus datos." if rol == "cliente"
           else "Tenés acceso completo. Usá /ayuda."),
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
            "`5400kg` (sin patentes)\n\n"
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
        await update.message.reply_text("Solo operarios y encargados pueden cambiar el lote.")
        return ConversationHandler.END
    await update.message.reply_text("¿Para qué cliente es esta cosecha? (nombre o apellido)")
    return CLIENTE

async def recibir_cliente(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    r = supabase.table("clientes").select("*").ilike("apellido", f"%{texto}%").execute()
    if not r.data:
        r = supabase.table("clientes").select("*").ilike("nombre", f"%{texto}%").execute()
    if not r.data:
        # Crear cliente nuevo
        partes = texto.split()
        nombre   = partes[0] if partes else texto
        apellido = " ".join(partes[1:]) if len(partes) > 1 else ""
        nuevo = supabase.table("clientes").insert({"nombre": nombre, "apellido": apellido}).execute()
        context.user_data["cliente_id"] = nuevo.data[0]["id"]
        await update.message.reply_text(
            f"Cliente *{texto}* creado. ¿En qué campo estamos cosechando?",
            parse_mode="Markdown"
        )
    elif len(r.data) == 1:
        context.user_data["cliente_id"] = r.data[0]["id"]
        await update.message.reply_text(
            f"Cliente: *{r.data[0]['nombre']} {r.data[0]['apellido']}*\n¿En qué campo?",
            parse_mode="Markdown"
        )
    else:
        nombres = "\n".join(f"- {x['nombre']} {x['apellido']}" for x in r.data)
        context.user_data["clientes_encontrados"] = r.data
        await update.message.reply_text(f"Encontré varios:\n{nombres}\n\nEscribí el apellido exacto.")
        return CLIENTE
    return CAMPO

async def recibir_campo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto      = update.message.text.strip()
    cliente_id = context.user_data["cliente_id"]
    r = supabase.table("campos").select("*").eq("cliente_id", cliente_id).ilike("nombre", f"%{texto}%").execute()
    if not r.data:
        nuevo = supabase.table("campos").insert({"nombre": texto, "cliente_id": cliente_id}).execute()
        context.user_data["campo_id"] = nuevo.data[0]["id"]
        await update.message.reply_text(f"Campo *{texto}* creado. ¿En qué lote?", parse_mode="Markdown")
    else:
        context.user_data["campo_id"] = r.data[0]["id"]
        await update.message.reply_text(
            f"Campo: *{r.data[0]['nombre']}*\n¿En qué lote?", parse_mode="Markdown"
        )
    return LOTE

async def recibir_lote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto    = update.message.text.strip()
    campo_id = context.user_data["campo_id"]
    r = supabase.table("lotes").select("*").eq("campo_id", campo_id).ilike("nombre", f"%{texto}%").execute()
    if not r.data:
        nuevo = supabase.table("lotes").insert({"nombre": texto, "campo_id": campo_id}).execute()
        context.user_data["lote_id"] = nuevo.data[0]["id"]
    else:
        context.user_data["lote_id"] = r.data[0]["id"]

    chat_id = str(update.effective_chat.id)
    supabase.table("sesion_activa").upsert({
        "chat_id":    chat_id,
        "cliente_id": context.user_data["cliente_id"],
        "campo_id":   context.user_data["campo_id"],
        "lote_id":    context.user_data["lote_id"],
        "destino":    None,
        "camion_id":  None,
        "silo_id":    None,
        "iniciada_at": ahora().isoformat()
    }).execute()

    teclado = [["Camión", "Silobolsa"]]
    await update.message.reply_text(
        f"✅ Sesión iniciada: *{texto}*\n¿Las descargas van a camión o silobolsa?",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(teclado, one_time_keyboard=True, resize_keyboard=True)
    )
    return DESTINO

async def recibir_destino(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto   = update.message.text.lower().strip()
    chat_id = str(update.effective_chat.id)

    if "silo" in texto:
        lote_id = context.user_data.get("lote_id") or get_sesion(chat_id)["lote_id"]
        r = supabase.table("silobolsas").select("numero").eq("lote_id", lote_id).order("numero", desc=True).execute()
        numero = (r.data[0]["numero"] + 1) if r.data else 1
        nuevo  = supabase.table("silobolsas").insert({"numero": numero, "lote_id": lote_id}).execute()
        silo_id = nuevo.data[0]["id"]
        supabase.table("sesion_activa").update({
            "destino": "silo", "silo_id": silo_id, "camion_id": None
        }).eq("chat_id", chat_id).execute()
        await update.message.reply_text(
            f"🌾 Silobolsa #{numero} abierto. Mandá las descargas.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "¿Patente del chasis?",
        reply_markup=ReplyKeyboardRemove()
    )
    context.user_data["destino_camion"] = True
    return PATENTE_CHASIS

async def recibir_patente_chasis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["patente_chasis"] = update.message.text.upper().strip()
    await update.message.reply_text("¿Patente del acoplado?")
    return PATENTE_ACOPLADO

async def recibir_patente_acoplado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["patente_acoplado"] = update.message.text.upper().strip()
    await update.message.reply_text("¿Capacidad del camión en kg? (ej: 30000) — o escribí 0 si no sabés")
    return CAPACIDAD

async def recibir_capacidad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    try:
        cap = float(update.message.text.strip().replace('.','').replace(',','.'))
    except ValueError:
        cap = 0

    chasis   = context.user_data["patente_chasis"]
    acoplado = context.user_data["patente_acoplado"]

    # Buscar si el camión ya existe
    r = supabase.table("camiones").select("*").eq("patente_chasis", chasis).eq("patente_acoplado", acoplado).execute()
    if r.data:
        camion_id = r.data[0]["id"]
        if cap > 0:
            supabase.table("camiones").update({"capacidad_kg": cap}).eq("id", camion_id).execute()
    else:
        nuevo = supabase.table("camiones").insert({
            "patente_chasis": chasis, "patente_acoplado": acoplado,
            "capacidad_kg": cap if cap > 0 else None
        }).execute()
        camion_id = nuevo.data[0]["id"]

    supabase.table("sesion_activa").update({
        "destino": "camion", "camion_id": camion_id, "silo_id": None
    }).eq("chat_id", chat_id).execute()

    await update.message.reply_text(
        f"🚛 Camión *{chasis} / {acoplado}* listo.\nMandá las descargas.",
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
    r = supabase.table("silobolsas").select("numero").eq("lote_id", lote_id).order("numero", desc=True).execute()
    numero  = (r.data[0]["numero"] + 1) if r.data else 1
    nuevo   = supabase.table("silobolsas").insert({"numero": numero, "lote_id": lote_id}).execute()
    silo_id = nuevo.data[0]["id"]
    supabase.table("sesion_activa").update({
        "destino": "silo", "silo_id": silo_id, "camion_id": None
    }).eq("chat_id", chat_id).execute()
    await update.message.reply_text(f"🌾 Silobolsa #{numero} abierto.")

# ── /nuevocamion ─────────────────────────────────────────────
async def cmd_nuevocamion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid     = str(update.effective_user.id)
    usuario = get_usuario(uid)
    if not usuario or usuario["rol"] not in ("operario", "encargado"):
        await update.message.reply_text("Solo operarios y encargados pueden hacer esto.")
        return ConversationHandler.END
    await update.message.reply_text("¿Patente del chasis del nuevo camión?")
    return NUEVO_CAMION_CHASIS

async def nuevo_camion_chasis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["patente_chasis"] = update.message.text.upper().strip()
    await update.message.reply_text("¿Patente del acoplado?")
    return NUEVO_CAMION_ACOPLADO

async def nuevo_camion_acoplado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["patente_acoplado"] = update.message.text.upper().strip()
    await update.message.reply_text("¿Capacidad en kg? (ej: 30000) — o escribí 0 si no sabés")
    return NUEVO_CAMION_CAP

async def nuevo_camion_cap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
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
        nuevo = supabase.table("camiones").insert({
            "patente_chasis": chasis, "patente_acoplado": acoplado,
            "capacidad_kg": cap if cap > 0 else None
        }).execute()
        camion_id = nuevo.data[0]["id"]
    supabase.table("sesion_activa").update({
        "destino": "camion", "camion_id": camion_id, "silo_id": None
    }).eq("chat_id", chat_id).execute()
    await update.message.reply_text(
        f"🚛 Camión *{chasis} / {acoplado}* activo.",
        parse_mode="Markdown"
    )
    return ConversationHandler.END

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

    args  = " ".join(context.args).lower() if context.args else ""
    ahora_ts = ahora()

    if "mes" in args:
        desde = ahora_ts.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        titulo = f"Mes {ahora_ts.strftime('%B %Y')}"
    elif "semana" in args:
        desde = ahora_ts - timedelta(days=7)
        titulo = "Últimos 7 días"
    else:
        desde = ahora_ts.replace(hour=0, minute=0, second=0, microsecond=0)
        titulo = f"Hoy {ahora_ts.strftime('%d/%m/%Y')}"

    q = (supabase.table("descargas")
         .select("kg, tolva, destino, camion_id, silobolsa_id, cliente_id, "
                 "camiones(patente_chasis,patente_acoplado), "
                 "clientes(nombre,apellido), "
                 "lotes(nombre), campos(nombre)")
         .gte("created_at", desde.isoformat()))

    if usuario["rol"] == "cliente":
        q = q.eq("cliente_id", usuario.get("cliente_id"))

    res = q.order("created_at", desc=True).execute()

    if not res.data:
        await update.message.reply_text(f"Sin registros para {titulo}.")
        return

    total_kg = sum(float(r["kg"]) for r in res.data)
    camiones_set = set()
    silos_set    = set()
    for r in res.data:
        if r["camion_id"]:   camiones_set.add(r["camion_id"])
        if r["silobolsa_id"]: silos_set.add(r["silobolsa_id"])

    lineas = [f"📊 *{titulo}*\n",
              f"Total: *{total_kg:,.0f} kg*",
              f"Camiones: {len(camiones_set)}  |  Silobolsas: {len(silos_set)}",
              f"Descargas: {len(res.data)}\n"]

    if usuario["rol"] == "encargado":
        clientes = {}
        for r in res.data:
            c = r.get("clientes")
            nombre = f"{c['nombre']} {c['apellido']}" if c else "Sin cliente"
            clientes.setdefault(nombre, 0)
            clientes[nombre] += float(r["kg"])
        for nombre, kg in sorted(clientes.items()):
            lineas.append(f"👤 *{nombre}*: {kg:,.0f} kg")

    await update.message.reply_text("\n".join(lineas), parse_mode="Markdown")

# ── Registro de descarga (mensaje libre) ─────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid     = str(update.effective_user.id)
    usuario = get_usuario(uid)

    if not usuario:
        await update.message.reply_text("No te conozco todavía. Escribí /start para registrarte.")
        return

    if usuario["rol"] == "cliente":
        await update.message.reply_text("Usá /resumen para consultar tus datos.")
        return

    chat_id = str(update.effective_chat.id)
    sesion  = get_sesion(chat_id)
    texto   = update.message.text or ""

    # Sin sesión activa → iniciar flujo
    if not sesion or not sesion.get("lote_id"):
        context.user_data.clear()
        await update.message.reply_text(
            "No hay sesión activa. ¿Para qué cliente es esta cosecha?"
        )
        return  # El ConversationHandler toma el control

    resultado = parsear_descarga(texto)
    if not resultado:
        if re.search(r'\d{3,}', texto):
            await update.message.reply_text(
                "⚠️ No entendí. Ejemplos:\n"
                "`AB123CD XY456ZW 5400kg` — camión\n"
                "`5400kg` — silobolsa activo",
                parse_mode="Markdown"
            )
        return

    kg, patentes = resultado
    ts = update.message.date.astimezone(ARG)

    # Determinar destino
    destino = sesion.get("destino")

    if patentes and len(patentes) >= 2:
        # Tiene dos patentes → camión
        chasis, acoplado = patentes[0], patentes[1]
        r = supabase.table("camiones").select("*").eq("patente_chasis", chasis).eq("patente_acoplado", acoplado).execute()
        if r.data:
            camion = r.data[0]
        else:
            nuevo  = supabase.table("camiones").insert({"patente_chasis": chasis, "patente_acoplado": acoplado}).execute()
            camion = nuevo.data[0]
        supabase.table("sesion_activa").update({
            "destino": "camion", "camion_id": camion["id"], "silo_id": None
        }).eq("chat_id", chat_id).execute()
        sesion["destino"]   = "camion"
        sesion["camion_id"] = camion["id"]
        sesion["camiones"]  = camion
        destino = "camion"

    elif not destino:
        await update.message.reply_text(
            "¿Este grano va a camión o silobolsa?\n"
            "Usá /nuevocamion o /nuevosilo para definirlo.",
        )
        return

    # Guardar descarga
    data = {
        "kg":          kg,
        "destino":     destino,
        "camion_id":   sesion.get("camion_id") if destino == "camion" else None,
        "silobolsa_id": sesion.get("silo_id") if destino == "silo" else None,
        "lote_id":     sesion.get("lote_id"),
        "campo_id":    sesion.get("campo_id"),
        "cliente_id":  sesion.get("cliente_id"),
        "tolva":       update.effective_chat.title or "directa",
        "operario_id": usuario["id"],
        "chat_id":     chat_id,
        "created_at":  ts.isoformat(),
    }
    supabase.table("descargas").insert(data).execute()

    # Armar respuesta
    cliente_obj = sesion.get("clientes") or {}
    cliente_str = f"{cliente_obj.get('nombre','')} {cliente_obj.get('apellido','')}".strip() or "—"
    campo_str   = (sesion.get("campos") or {}).get("nombre", "—")
    lote_str    = (sesion.get("lotes") or {}).get("nombre", "—")

    if destino == "camion":
        camion_obj  = sesion.get("camiones") or {}
        acumulado   = kg_acumulado_camion(sesion["camion_id"], chat_id) + kg
        capacidad   = camion_obj.get("capacidad_kg")
        chasis_str  = camion_obj.get("patente_chasis", "—")
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
        acumulado = kg_acumulado_silo(sesion["silo_id"]) + kg
        lineas = [
            f"✅ *{cliente_str} / {campo_str} / {lote_str}*",
            f"🌾 Silobolsa #{silo_num}",
            f"Esta carga:  *{kg:,.0f} kg*",
            f"Acumulado:   *{acumulado:,.0f} kg*",
        ]

    await update.message.reply_text("\n".join(lineas), parse_mode="Markdown")

# ── Main ─────────────────────────────────────────────────────
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    registro_conv = ConversationHandler(
        entry_points=[CommandHandler("start", cmd_start)],
        states={
            ROL:    [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_rol)],
            NOMBRE: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_nombre)],
        },
        fallbacks=[]
    )

    lote_conv = ConversationHandler(
        entry_points=[CommandHandler("nuevolote", cmd_nuevolote)],
        states={
            CLIENTE:          [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_cliente)],
            CAMPO:            [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_campo)],
            LOTE:             [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_lote)],
            DESTINO:          [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_destino)],
            PATENTE_CHASIS:   [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_patente_chasis)],
            PATENTE_ACOPLADO: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_patente_acoplado)],
            CAPACIDAD:        [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_capacidad)],
        },
        fallbacks=[]
    )

    camion_conv = ConversationHandler(
        entry_points=[CommandHandler("nuevocamion", cmd_nuevocamion)],
        states={
            NUEVO_CAMION_CHASIS:   [MessageHandler(filters.TEXT & ~filters.COMMAND, nuevo_camion_chasis)],
            NUEVO_CAMION_ACOPLADO: [MessageHandler(filters.TEXT & ~filters.COMMAND, nuevo_camion_acoplado)],
            NUEVO_CAMION_CAP:      [MessageHandler(filters.TEXT & ~filters.COMMAND, nuevo_camion_cap)],
        },
        fallbacks=[]
    )

    app.add_handler(registro_conv)
    app.add_handler(lote_conv)
    app.add_handler(camion_conv)
    app.add_handler(CommandHandler("ayuda",      cmd_ayuda))
    app.add_handler(CommandHandler("resumen",    cmd_resumen))
    app.add_handler(CommandHandler("nuevosilo",  cmd_nuevosilo))
    app.add_handler(CommandHandler("camion",     cmd_camion))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot corriendo...")
    app.run_polling()
