import os, re, logging
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
  CONT_MENU,
  CONT_ADD_OP_TEL, CONT_ADD_OP_NOMBRE,
  CONT_ADD_CLI_TEL, CONT_ADD_CLI_NOMBRE, CONT_ADD_CLI_APELLIDO,
) = range(8)

def ahora():
    return datetime.now(ARG)

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

def get_usuario_by_telefono(telefono: str, contratista_id: int):
    tel = limpiar_telefono(telefono)
    r   = supabase.table("usuarios").select("*").eq("telefono", tel).eq("contratista_id", contratista_id).execute()
    return r.data[0] if r.data else None

def get_cliente_by_telefono(telefono: str, contratista_id: int):
    tel = limpiar_telefono(telefono)
    r   = supabase.table("clientes").select("*").eq("telefono", tel).eq("contratista_id", contratista_id).execute()
    return r.data[0] if r.data else None

def limpiar_telefono(tel: str) -> str:
    return re.sub(r'\D', '', tel)

def teclado_roles():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏭 Contratista / Dueño del equipo", callback_data="rol_contratista")],
        [InlineKeyboardButton("🌾 Operario de tolva",              callback_data="rol_operario")],
        [InlineKeyboardButton("👤 Cliente / Dueño de granos",      callback_data="rol_cliente")],
    ])

def teclado_menu_contratista():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Agregar operario", callback_data="cont_add_op")],
        [InlineKeyboardButton("➕ Agregar cliente",  callback_data="cont_add_cli")],
        [InlineKeyboardButton("👷 Ver mis operarios", callback_data="cont_ver_op")],
        [InlineKeyboardButton("👤 Ver mis clientes",  callback_data="cont_ver_cli")],
    ])

# ── Registro nuevo usuario ───────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)

    # Ya registrado como contratista
    cont = get_contratista(uid)
    if cont:
        await update.message.reply_text(
            f"Hola {cont['nombre']}! Ya estás registrado como contratista.",
            reply_markup=teclado_menu_contratista()
        )
        return ConversationHandler.END

    # Ya registrado como operario
    usr = get_usuario(uid)
    if usr:
        await update.message.reply_text(
            f"Hola {usr['nombre']}! Ya estás registrado como operario.\n"
            "Próximamente podrás registrar descargas desde acá."
        )
        return ConversationHandler.END

    # Ya registrado como cliente
    cli = get_cliente_by_telegram(uid)
    if cli:
        await update.message.reply_text(
            f"Hola {cli['nombre']}! Ya estás registrado como cliente.\n"
            "Próximamente podrás consultar tus datos desde acá."
        )
        return ConversationHandler.END

    # Nuevo usuario
    await update.message.reply_text(
        "Hola! Bienvenido al sistema de tolvas.\n\n¿Quién sos?",
        reply_markup=teclado_roles()
    )
    return REG_ROL

async def handle_mensaje_no_registrado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hola! Bienvenido al sistema de tolvas.\n\n¿Quién sos?",
        reply_markup=teclado_roles()
    )
    return REG_ROL

async def elegir_rol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    rol   = query.data.replace("rol_", "")
    context.user_data["rol_elegido"] = rol

    if rol == "contratista":
        await query.edit_message_text("¿Cuál es tu nombre y apellido?")
        return REG_NOMBRE

    elif rol == "operario":
        await query.edit_message_text(
            "Para acceder como operario, tu contratista debe haberte registrado primero.\n\n"
            "Si ya fuiste registrado, tu acceso se habilitará automáticamente cuando escribas aquí.\n"
            "Si no, contactá a tu contratista."
        )
        return ConversationHandler.END

    elif rol == "cliente":
        await query.edit_message_text(
            "Para acceder como cliente, tu contratista debe haberte registrado primero.\n\n"
            "Si ya fuiste registrado, tu acceso se habilitará automáticamente cuando escribas aquí.\n"
            "Si no, contactá a tu contratista."
        )
        return ConversationHandler.END

    return ConversationHandler.END

async def recibir_nombre_contratista(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto  = update.message.text.strip()
    partes = texto.split()
    nombre   = partes[0]
    apellido = " ".join(partes[1:]) if len(partes) > 1 else ""
    uid      = str(update.effective_user.id)

    supabase.table("contratistas").insert({
        "nombre":      nombre,
        "apellido":    apellido,
        "telegram_id": uid,
    }).execute()

    await update.message.reply_text(
        f"✅ Bienvenido *{nombre} {apellido}*!\n\n"
        "Ya estás registrado como contratista. ¿Qué querés hacer?",
        parse_mode="Markdown",
        reply_markup=teclado_menu_contratista()
    )
    return ConversationHandler.END

# ── Menú contratista ─────────────────────────────────────────
async def menu_contratista_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    uid     = str(update.effective_user.id)
    cont    = get_contratista(uid)
    accion  = query.data

    if not cont:
        await query.edit_message_text("No se encontró tu cuenta de contratista. Escribí /start.")
        return ConversationHandler.END

    if accion == "cont_add_op":
        await query.edit_message_text(
            "¿Cuál es el número de teléfono del operario?\n"
            "Escribilo con código de área, ej: `1123456789`",
            parse_mode="Markdown"
        )
        context.user_data["contratista_id"] = cont["id"]
        return CONT_ADD_OP_TEL

    elif accion == "cont_add_cli":
        await query.edit_message_text(
            "¿Cuál es el número de teléfono del cliente?\n"
            "Escribilo con código de área, ej: `1123456789`",
            parse_mode="Markdown"
        )
        context.user_data["contratista_id"] = cont["id"]
        return CONT_ADD_CLI_TEL

    elif accion == "cont_ver_op":
        r = supabase.table("usuarios").select("*").eq("contratista_id", cont["id"]).eq("rol", "operario").execute()
        if not r.data:
            await query.edit_message_text(
                "No tenés operarios registrados todavía.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Volver", callback_data="cont_volver")]])
            )
        else:
            lineas = ["👷 *Mis operarios*\n"]
            for op in r.data:
                tel = f" — {op['telefono']}" if op.get("telefono") else ""
                lineas.append(f"• {op['nombre']}{tel}")
            await query.edit_message_text(
                "\n".join(lineas),
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Volver", callback_data="cont_volver")]])
            )

    elif accion == "cont_ver_cli":
        r = supabase.table("clientes").select("*").eq("contratista_id", cont["id"]).execute()
        if not r.data:
            await query.edit_message_text(
                "No tenés clientes registrados todavía.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Volver", callback_data="cont_volver")]])
            )
        else:
            lineas = ["👤 *Mis clientes*\n"]
            for cli in r.data:
                tel = f" — {cli['telefono']}" if cli.get("telefono") else " — sin teléfono"
                lineas.append(f"• {cli['nombre']} {cli['apellido']}{tel}")
            await query.edit_message_text(
                "\n".join(lineas),
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Volver", callback_data="cont_volver")]])
            )

    elif accion == "cont_volver":
        await query.edit_message_text(
            "¿Qué querés hacer?",
            reply_markup=teclado_menu_contratista()
        )

    return ConversationHandler.END

# ── Agregar operario ─────────────────────────────────────────
async def add_op_telefono(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tel = limpiar_telefono(update.message.text.strip())
    if len(tel) < 8:
        await update.message.reply_text("El número no parece válido. Intentá de nuevo, ej: `1123456789`", parse_mode="Markdown")
        return CONT_ADD_OP_TEL

    contratista_id = context.user_data["contratista_id"]

    # Verificar si ya existe
    existente = get_usuario_by_telefono(tel, contratista_id)
    if existente:
        await update.message.reply_text(
            f"El número {tel} ya está registrado como operario: *{existente['nombre']}*",
            parse_mode="Markdown",
            reply_markup=teclado_menu_contratista()
        )
        return ConversationHandler.END

    context.user_data["nuevo_op_tel"] = tel
    await update.message.reply_text("¿Cuál es el nombre y apellido del operario?")
    return CONT_ADD_OP_NOMBRE

async def add_op_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto          = update.message.text.strip()
    tel            = context.user_data["nuevo_op_tel"]
    contratista_id = context.user_data["contratista_id"]

    supabase.table("usuarios").insert({
        "nombre":        texto,
        "telefono":      tel,
        "rol":           "operario",
        "contratista_id": contratista_id,
        "activo":        True,
    }).execute()

    await update.message.reply_text(
        f"✅ Operario *{texto}* registrado con el número {tel}.\n\n"
        "Cuando esta persona escriba al bot, va a tener acceso automáticamente.",
        parse_mode="Markdown",
        reply_markup=teclado_menu_contratista()
    )
    return ConversationHandler.END

# ── Agregar cliente ──────────────────────────────────────────
async def add_cli_telefono(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tel = limpiar_telefono(update.message.text.strip())
    if len(tel) < 8:
        await update.message.reply_text("El número no parece válido. Intentá de nuevo, ej: `1123456789`", parse_mode="Markdown")
        return CONT_ADD_CLI_TEL

    contratista_id = context.user_data["contratista_id"]

    # Verificar si ya existe
    existente = get_cliente_by_telefono(tel, contratista_id)
    if existente:
        await update.message.reply_text(
            f"El número {tel} ya está registrado: *{existente['nombre']} {existente['apellido']}*",
            parse_mode="Markdown",
            reply_markup=teclado_menu_contratista()
        )
        return ConversationHandler.END

    context.user_data["nuevo_cli_tel"] = tel
    await update.message.reply_text("¿Cuál es el *nombre* del cliente?", parse_mode="Markdown")
    return CONT_ADD_CLI_NOMBRE

async def add_cli_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["nuevo_cli_nombre"] = update.message.text.strip()
    await update.message.reply_text("¿Cuál es el *apellido*?", parse_mode="Markdown")
    return CONT_ADD_CLI_APELLIDO

async def add_cli_apellido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    apellido       = update.message.text.strip()
    nombre         = context.user_data["nuevo_cli_nombre"]
    tel            = context.user_data["nuevo_cli_tel"]
    contratista_id = context.user_data["contratista_id"]

    supabase.table("clientes").insert({
        "nombre":          nombre,
        "apellido":        apellido,
        "telefono":        tel,
        "contratista_id":  contratista_id,
    }).execute()

    await update.message.reply_text(
        f"✅ Cliente *{nombre} {apellido}* registrado con el número {tel}.\n\n"
        "Cuando esta persona escriba al bot, va a tener acceso automáticamente.",
        parse_mode="Markdown",
        reply_markup=teclado_menu_contratista()
    )
    return ConversationHandler.END

# ── Handler de mensajes libres ───────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = str(update.effective_user.id)
    # Obtener número de teléfono de Telegram si está disponible
    tel_tg = update.effective_user.phone_number or ""

    # Verificar si es contratista
    cont = get_contratista(uid)
    if cont:
        await update.message.reply_text(
            f"Hola {cont['nombre']}! ¿Qué querés hacer?",
            reply_markup=teclado_menu_contratista()
        )
        return

    # Verificar si es operario por telegram_id
    usr = get_usuario(uid)
    if usr:
        await update.message.reply_text(
            f"Hola {usr['nombre']}! Sos operario de *{(usr.get('contratistas') or {}).get('nombre','')}*.\n"
            "Próximamente podrás registrar descargas desde acá.",
            parse_mode="Markdown"
        )
        return

    # Verificar si es cliente por telegram_id
    cli = get_cliente_by_telegram(uid)
    if cli:
        await update.message.reply_text(
            f"Hola {cli['nombre']}! Sos cliente de *{(cli.get('contratistas') or {}).get('nombre','')}*.\n"
            "Próximamente podrás consultar tus datos desde acá.",
            parse_mode="Markdown"
        )
        return

    # No registrado → mostrar opciones
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
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
        ],
        states={
            REG_ROL:    [CallbackQueryHandler(elegir_rol, pattern="^rol_")],
            REG_NOMBRE: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_nombre_contratista)],
        },
        fallbacks=[CommandHandler("start", cmd_start)]
    )

    add_op_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(menu_contratista_callback, pattern="^cont_")],
        states={
            CONT_ADD_OP_TEL:    [MessageHandler(filters.TEXT & ~filters.COMMAND, add_op_telefono)],
            CONT_ADD_OP_NOMBRE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_op_nombre)],
            CONT_ADD_CLI_TEL:      [MessageHandler(filters.TEXT & ~filters.COMMAND, add_cli_telefono)],
            CONT_ADD_CLI_NOMBRE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, add_cli_nombre)],
            CONT_ADD_CLI_APELLIDO: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_cli_apellido)],
        },
        fallbacks=[CommandHandler("start", cmd_start)]
    )

    app.add_handler(registro_conv)
    app.add_handler(add_op_conv)

    print("Bot corriendo...")
    app.run_polling()
