import os, re, random, logging
from datetime import datetime, timezone, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (ApplicationBuilder, MessageHandler, CommandHandler,
                          ConversationHandler, CallbackQueryHandler,
                          filters, ContextTypes)
from supabase import create_client

TOKEN        = os.environ["TELEGRAM_TOKEN"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
logging.basicConfig(level=logging.INFO)
ARG = timezone(timedelta(hours=-3))

# ── Estados ──────────────────────────────────────────────────
(
    REG_ROL, REG_NOMBRE,
    ADD_OP_NOMBRE, ADD_OP_SOY_YO,
    ADD_CLI_NOMBRE, ADD_CLI_SOY_YO,
    INGRESAR_CODIGO,
) = range(7)

def ahora():
    return datetime.now(ARG)

def generar_codigo():
    return str(random.randint(1000, 9999))

# ── BD helpers ───────────────────────────────────────────────
def get_contratista(telegram_id: str):
    r = supabase.table("contratistas").select("*").eq("telegram_id", telegram_id).execute()
    return r.data[0] if r.data else None

def get_usuario(telegram_id: str):
    r = supabase.table("usuarios").select("*, contratistas(nombre,apellido)").eq("telegram_id", telegram_id).execute()
    return r.data[0] if r.data else None

def get_cliente_by_telegram(telegram_id: str):
    r = supabase.table("clientes").select("*, contratistas(nombre,apellido)").eq("telegram_id", telegram_id).execute()
    return r.data[0] if r.data else None

def get_operarios(contratista_id: int):
    r = supabase.table("usuarios").select("*").eq("contratista_id", contratista_id).eq("rol", "operario").execute()
    return r.data or []

def get_clientes(contratista_id: int):
    r = supabase.table("clientes").select("*").eq("contratista_id", contratista_id).execute()
    return r.data or []

def es_operario(telegram_id: str):
    r = supabase.table("usuarios").select("id").eq("telegram_id", telegram_id).eq("rol", "operario").execute()
    return bool(r.data)

def teclado_menu_contratista(contratista_id: int, telegram_id: str):
    operarios = get_operarios(contratista_id)
    clientes  = get_clientes(contratista_id)
    botones   = []

    if operarios:
        botones.append([InlineKeyboardButton(f"👷 Mis operarios ({len(operarios)})", callback_data="cont_ver_op")])
    else:
        botones.append([InlineKeyboardButton("👷 Mis operarios (0)", callback_data="cont_ver_op")])

    if clientes:
        botones.append([InlineKeyboardButton(f"👤 Mis clientes ({len(clientes)})", callback_data="cont_ver_cli")])
    else:
        botones.append([InlineKeyboardButton("👤 Mis clientes (0)", callback_data="cont_ver_cli")])

    if es_operario(telegram_id):
        botones.append([InlineKeyboardButton("📦 Agregar descarga", callback_data="cont_descarga")])

    return InlineKeyboardMarkup(botones)

def teclado_roles():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏭 Contratista / Dueño del equipo", callback_data="rol_contratista")],
        [InlineKeyboardButton("🌾 Operario de tolva",              callback_data="rol_operario")],
        [InlineKeyboardButton("👤 Cliente / Dueño de granos",      callback_data="rol_cliente")],
    ])

# ── /start ───────────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = str(update.effective_user.id)
    cont = get_contratista(uid)
    if cont:
        await update.message.reply_text(
            f"Hola {cont['nombre']}! ¿Qué querés hacer?",
            reply_markup=teclado_menu_contratista(cont["id"], uid)
        )
        return ConversationHandler.END

    usr = get_usuario(uid)
    if usr:
        cont_nombre = (usr.get("contratistas") or {}).get("nombre", "")
        await update.message.reply_text(
            f"Hola {usr['nombre']}! Sos operario de *{cont_nombre}*.\n"
            "Próximamente podrás registrar descargas desde acá.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    cli = get_cliente_by_telegram(uid)
    if cli:
        cont_nombre = (cli.get("contratistas") or {}).get("nombre", "")
        await update.message.reply_text(
            f"Hola {cli['nombre']}! Sos cliente de *{cont_nombre}*.\n"
            "Próximamente podrás consultar tus datos desde acá.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "Hola! Bienvenido al sistema de tolvas.\n\n¿Quién sos?",
        reply_markup=teclado_roles()
    )
    return REG_ROL

# ── Registro ─────────────────────────────────────────────────
async def elegir_rol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    rol   = query.data.replace("rol_", "")

    if rol == "contratista":
        await query.edit_message_text("¿Cuál es tu nombre y apellido?")
        return REG_NOMBRE

    elif rol in ("operario", "cliente"):
        await query.edit_message_text(
            "Para acceder necesitás un código de acceso que te da tu contratista.\n\n"
            "Ingresá tu código:"
        )
        context.user_data["rol_pendiente"] = rol
        return INGRESAR_CODIGO

    return ConversationHandler.END

async def recibir_nombre_contratista(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto    = update.message.text.strip()
    partes   = texto.split()
    nombre   = partes[0]
    apellido = " ".join(partes[1:]) if len(partes) > 1 else ""
    uid      = str(update.effective_user.id)

    supabase.table("contratistas").insert({
        "nombre":      nombre,
        "apellido":    apellido,
        "telegram_id": uid,
    }).execute()

    cont = get_contratista(uid)
    await update.message.reply_text(
        f"✅ Bienvenido *{nombre} {apellido}*! Quedaste registrado como contratista.",
        parse_mode="Markdown",
        reply_markup=teclado_menu_contratista(cont["id"], uid)
    )
    return ConversationHandler.END

async def ingresar_codigo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    codigo = update.message.text.strip()
    uid    = str(update.effective_user.id)

    # Buscar código en operarios
    r = supabase.table("usuarios").select("*").eq("codigo_acceso", codigo).is_("telegram_id", "null").execute()
    if r.data:
        usuario = r.data[0]
        supabase.table("usuarios").update({"telegram_id": uid}).eq("id", usuario["id"]).execute()
        await update.message.reply_text(
            f"✅ Bienvenido *{usuario['nombre']}*! Ya tenés acceso como operario.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    # Buscar código en clientes
    r = supabase.table("clientes").select("*").eq("codigo_acceso", codigo).is_("telegram_id", "null").execute()
    if r.data:
        cliente = r.data[0]
        supabase.table("clientes").update({"telegram_id": uid}).eq("id", cliente["id"]).execute()
        await update.message.reply_text(
            f"✅ Bienvenido *{cliente['nombre']} {cliente['apellido']}*! Ya tenés acceso como cliente.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "Código incorrecto o ya fue usado. Pedile a tu contratista que te dé el código correcto."
    )
    return INGRESAR_CODIGO

# ── Menú contratista callbacks ───────────────────────────────
async def menu_contratista_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    uid     = str(update.effective_user.id)
    cont    = get_contratista(uid)
    accion  = query.data

    if not cont:
        await query.edit_message_text("No se encontró tu cuenta. Escribí /start.")
        return ConversationHandler.END

    if accion == "cont_ver_op":
        operarios = get_operarios(cont["id"])
        botones   = []
        if operarios:
            lineas = ["👷 *Mis operarios*\n"]
            for op in operarios:
                vinculado = "✅" if op.get("telegram_id") else "⏳"
                lineas.append(f"{vinculado} {op['nombre']}")
            texto = "\n".join(lineas)
        else:
            texto = "No tenés operarios registrados todavía."
        botones.append([InlineKeyboardButton("➕ Agregar operario", callback_data="cont_add_op")])
        botones.append([InlineKeyboardButton("⬅️ Volver",           callback_data="cont_volver")])
        await query.edit_message_text(texto, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(botones))
        return ConversationHandler.END

    elif accion == "cont_ver_cli":
        clientes = get_clientes(cont["id"])
        botones  = []
        if clientes:
            lineas = ["👤 *Mis clientes*\n"]
            for cli in clientes:
                vinculado = "✅" if cli.get("telegram_id") else "⏳"
                lineas.append(f"{vinculado} {cli['nombre']} {cli['apellido']}")
            texto = "\n".join(lineas)
        else:
            texto = "No tenés clientes registrados todavía."
        botones.append([InlineKeyboardButton("➕ Agregar cliente", callback_data="cont_add_cli")])
        botones.append([InlineKeyboardButton("⬅️ Volver",          callback_data="cont_volver")])
        await query.edit_message_text(texto, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(botones))
        return ConversationHandler.END

    elif accion == "cont_add_op":
        await query.edit_message_text("¿Nombre y apellido del operario?")
        context.user_data["contratista_id"] = cont["id"]
        return ADD_OP_NOMBRE

    elif accion == "cont_add_cli":
        await query.edit_message_text("¿Nombre y apellido del cliente?")
        context.user_data["contratista_id"] = cont["id"]
        return ADD_CLI_NOMBRE

    elif accion == "cont_volver":
        await query.edit_message_text(
            "¿Qué querés hacer?",
            reply_markup=teclado_menu_contratista(cont["id"], uid)
        )
        return ConversationHandler.END

    elif accion == "cont_descarga":
        await query.edit_message_text("Función de descargas próximamente.")
        return ConversationHandler.END

    return ConversationHandler.END

# ── Agregar operario ─────────────────────────────────────────
async def add_op_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["nuevo_nombre"] = update.message.text.strip()
    teclado = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Sí, soy yo",        callback_data="op_soy_yo")],
        [InlineKeyboardButton("❌ No, es otra persona", callback_data="op_otro")],
    ])
    await update.message.reply_text(
        f"¿El operario *{context.user_data['nuevo_nombre']}* sos vos mismo?",
        parse_mode="Markdown",
        reply_markup=teclado
    )
    return ADD_OP_SOY_YO

async def add_op_soy_yo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query          = update.callback_query
    await query.answer()
    uid            = str(update.effective_user.id)
    nombre         = context.user_data["nuevo_nombre"]
    contratista_id = context.user_data["contratista_id"]
    partes         = nombre.split()

    if query.data == "op_soy_yo":
        # Verificar si ya es operario de este contratista
        r = supabase.table("usuarios").select("*").eq("telegram_id", uid).eq("contratista_id", contratista_id).execute()
        if r.data:
            await query.edit_message_text(
                f"Ya estás registrado como operario.",
                reply_markup=teclado_menu_contratista(contratista_id, uid)
            )
            return ConversationHandler.END

        supabase.table("usuarios").insert({
            "nombre":          partes[0],
            "rol":             "operario",
            "telegram_id":     uid,
            "contratista_id":  contratista_id,
            "activo":          True,
        }).execute()
        await query.edit_message_text(
            f"✅ Quedaste registrado como operario.",
            reply_markup=teclado_menu_contratista(contratista_id, uid)
        )
    else:
        codigo = generar_codigo()
        supabase.table("usuarios").insert({
            "nombre":          partes[0],
            "rol":             "operario",
            "codigo_acceso":   codigo,
            "contratista_id":  contratista_id,
            "activo":          True,
        }).execute()
        await query.edit_message_text(
            f"✅ Operario *{nombre}* creado.\n\n"
            f"Código de acceso: *{codigo}*\n"
            "Compartíselo para que ingrese al bot.",
            parse_mode="Markdown",
            reply_markup=teclado_menu_contratista(contratista_id, uid)
        )

    return ConversationHandler.END

# ── Agregar cliente ──────────────────────────────────────────
async def add_cli_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["nuevo_nombre"] = update.message.text.strip()
    teclado = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Sí, soy yo",         callback_data="cli_soy_yo")],
        [InlineKeyboardButton("❌ No, es otra persona", callback_data="cli_otro")],
    ])
    await update.message.reply_text(
        f"¿El cliente *{context.user_data['nuevo_nombre']}* sos vos mismo?",
        parse_mode="Markdown",
        reply_markup=teclado
    )
    return ADD_CLI_SOY_YO

async def add_cli_soy_yo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query          = update.callback_query
    await query.answer()
    uid            = str(update.effective_user.id)
    nombre         = context.user_data["nuevo_nombre"]
    contratista_id = context.user_data["contratista_id"]
    partes         = nombre.split()
    nombre_p       = partes[0]
    apellido_p     = " ".join(partes[1:]) if len(partes) > 1 else ""

    if query.data == "cli_soy_yo":
        r = supabase.table("clientes").select("*").eq("telegram_id", uid).eq("contratista_id", contratista_id).execute()
        if r.data:
            await query.edit_message_text(
                "Ya estás registrado como cliente.",
                reply_markup=teclado_menu_contratista(contratista_id, uid)
            )
            return ConversationHandler.END

        supabase.table("clientes").insert({
            "nombre":          nombre_p,
            "apellido":        apellido_p,
            "telegram_id":     uid,
            "contratista_id":  contratista_id,
        }).execute()
        await query.edit_message_text(
            f"✅ Quedaste registrado como cliente.",
            reply_markup=teclado_menu_contratista(contratista_id, uid)
        )
    else:
        codigo = generar_codigo()
        supabase.table("clientes").insert({
            "nombre":          nombre_p,
            "apellido":        apellido_p,
            "codigo_acceso":   codigo,
            "contratista_id":  contratista_id,
        }).execute()
        await query.edit_message_text(
            f"✅ Cliente *{nombre}* creado.\n\n"
            f"Código de acceso: *{codigo}*\n"
            "Compartíselo para que ingrese al bot.",
            parse_mode="Markdown",
            reply_markup=teclado_menu_contratista(contratista_id, uid)
        )

    return ConversationHandler.END

# ── Handler mensajes libres ──────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = str(update.effective_user.id)

    cont = get_contratista(uid)
    if cont:
        await update.message.reply_text(
            f"Hola {cont['nombre']}! ¿Qué querés hacer?",
            reply_markup=teclado_menu_contratista(cont["id"], uid)
        )
        return

    usr = get_usuario(uid)
    if usr:
        cont_nombre = (usr.get("contratistas") or {}).get("nombre", "")
        await update.message.reply_text(
            f"Hola {usr['nombre']}! Sos operario de *{cont_nombre}*.\n"
            "Próximamente podrás registrar descargas desde acá.",
            parse_mode="Markdown"
        )
        return

    cli = get_cliente_by_telegram(uid)
    if cli:
        cont_nombre = (cli.get("contratistas") or {}).get("nombre", "")
        await update.message.reply_text(
            f"Hola {cli['nombre']}! Sos cliente de *{cont_nombre}*.\n"
            "Próximamente podrás consultar tus datos desde acá.",
            parse_mode="Markdown"
        )
        return

    await update.message.reply_text(
        "Hola! Bienvenido al sistema de tolvas.\n\n¿Quién sos?",
        reply_markup=teclado_roles()
    )

# ── Main ─────────────────────────────────────────────────────
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    registro_conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", cmd_start),
            CallbackQueryHandler(elegir_rol, pattern="^rol_"),
        ],
        states={
            REG_ROL:         [CallbackQueryHandler(elegir_rol, pattern="^rol_")],
            REG_NOMBRE:      [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_nombre_contratista)],
            INGRESAR_CODIGO: [MessageHandler(filters.TEXT & ~filters.COMMAND, ingresar_codigo)],
        },
        fallbacks=[CommandHandler("start", cmd_start)],
        per_message=False
    )

    menu_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(menu_contratista_callback, pattern="^cont_")],
        states={
            ADD_OP_NOMBRE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, add_op_nombre)],
            ADD_OP_SOY_YO:  [CallbackQueryHandler(add_op_soy_yo, pattern="^op_")],
            ADD_CLI_NOMBRE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_cli_nombre)],
            ADD_CLI_SOY_YO: [CallbackQueryHandler(add_cli_soy_yo, pattern="^cli_")],
        },
        fallbacks=[CommandHandler("start", cmd_start)],
        per_message=False
    )

    app.add_handler(registro_conv)
    app.add_handler(menu_conv)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot corriendo...")
    app.run_polling()
