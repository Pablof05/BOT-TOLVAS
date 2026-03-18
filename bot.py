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

(
    REG_ROL, REG_NOMBRE,
    ADD_OP_NOMBRE, ADD_OP_SOY_YO,
    ADD_CLI_NOMBRE, ADD_CLI_SOY_YO,
    INGRESAR_CODIGO,
    CONFIRMAR_NOMBRE, CORREGIR_NOMBRE,
) = range(9)

def generar_codigo():
    return str(random.randint(1000, 9999))

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
    botones   = [
        [InlineKeyboardButton(f"👷 Mis operarios ({len(operarios)})", callback_data="cont_ver_op")],
        [InlineKeyboardButton(f"👤 Mis clientes ({len(clientes)})",   callback_data="cont_ver_cli")],
    ]
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
            f"Hola {cli['nombre']} {cli['apellido']}! Sos cliente de *{cont_nombre}*.\n"
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
    await query.edit_message_text("Ingresá el código de acceso que te dio tu contratista:")
    context.user_data["rol_pendiente"] = rol
    return INGRESAR_CODIGO

async def recibir_nombre_contratista(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto    = update.message.text.strip()
    partes   = texto.split()
    nombre   = partes[0]
    apellido = " ".join(partes[1:]) if len(partes) > 1 else ""
    uid      = str(update.effective_user.id)
    supabase.table("contratistas").insert({
        "nombre": nombre, "apellido": apellido, "telegram_id": uid,
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

    r = supabase.table("usuarios").select("*").eq("codigo_acceso", codigo).is_("telegram_id", "null").execute()
    if r.data:
        usuario = r.data[0]
        context.user_data["codigo_encontrado_id"]     = usuario["id"]
        context.user_data["codigo_encontrado_tipo"]   = "operario"
        context.user_data["codigo_encontrado_nombre"] = usuario["nombre"]
        teclado = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Sí, está bien",      callback_data="nombre_ok")],
            [InlineKeyboardButton("✏️ Corregir mi nombre", callback_data="nombre_corregir")],
        ])
        await update.message.reply_text(
            f"✅ Código correcto. Tu contratista te registró como:\n\n*{usuario['nombre']}*\n\n¿Es correcto tu nombre?",
            parse_mode="Markdown", reply_markup=teclado
        )
        return CONFIRMAR_NOMBRE

    r = supabase.table("clientes").select("*").eq("codigo_acceso", codigo).is_("telegram_id", "null").execute()
    if r.data:
        cliente = r.data[0]
        context.user_data["codigo_encontrado_id"]     = cliente["id"]
        context.user_data["codigo_encontrado_tipo"]   = "cliente"
        context.user_data["codigo_encontrado_nombre"] = f"{cliente['nombre']} {cliente['apellido']}"
        teclado = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Sí, está bien",      callback_data="nombre_ok")],
            [InlineKeyboardButton("✏️ Corregir mi nombre", callback_data="nombre_corregir")],
        ])
        await update.message.reply_text(
            f"✅ Código correcto. Tu contratista te registró como:\n\n*{cliente['nombre']} {cliente['apellido']}*\n\n¿Es correcto tu nombre?",
            parse_mode="Markdown", reply_markup=teclado
        )
        return CONFIRMAR_NOMBRE

    await update.message.reply_text(
        "Código incorrecto o ya fue usado.\nPedile a tu contratista el código correcto e intentá de nuevo:"
    )
    return INGRESAR_CODIGO

async def confirmar_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "nombre_corregir":
        await query.edit_message_text("¿Cuál es tu nombre y apellido correcto?")
        return CORREGIR_NOMBRE
    uid = str(update.effective_user.id)
    await _vincular_usuario(uid, context, None, query)
    return ConversationHandler.END

async def corregir_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    await _vincular_usuario(uid, context, update.message.text.strip(), None, update.message)
    return ConversationHandler.END

async def _vincular_usuario(uid, context, nombre_nuevo, query=None, msg=None):
    tipo   = context.user_data["codigo_encontrado_tipo"]
    rec_id = context.user_data["codigo_encontrado_id"]

    if tipo == "operario":
        update_data = {"telegram_id": uid, "codigo_acceso": None}
        if nombre_nuevo:
            update_data["nombre"] = nombre_nuevo.split()[0]
        supabase.table("usuarios").update(update_data).eq("id", rec_id).execute()
        r    = supabase.table("usuarios").select("nombre").eq("id", rec_id).execute()
        nombre_final = r.data[0]["nombre"] if r.data else ""
        texto = f"✅ Bienvenido *{nombre_final}*! Ya tenés acceso como operario."
    else:
        update_data = {"telegram_id": uid, "codigo_acceso": None}
        if nombre_nuevo:
            partes = nombre_nuevo.split()
            update_data["nombre"]   = partes[0]
            update_data["apellido"] = " ".join(partes[1:]) if len(partes) > 1 else ""
        supabase.table("clientes").update(update_data).eq("id", rec_id).execute()
        r = supabase.table("clientes").select("nombre,apellido").eq("id", rec_id).execute()
        c = r.data[0] if r.data else {}
        nombre_final = f"{c.get('nombre','')} {c.get('apellido','')}".strip()
        texto = f"✅ Bienvenido *{nombre_final}*! Ya tenés acceso como cliente."

    if query:
        await query.edit_message_text(texto, parse_mode="Markdown")
    elif msg:
        await msg.reply_text(texto, parse_mode="Markdown")

# ── Menú contratista ─────────────────────────────────────────
async def menu_contratista_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    uid    = str(update.effective_user.id)
    cont   = get_contratista(uid)
    accion = query.data

    if not cont:
        await query.edit_message_text("No se encontró tu cuenta. Escribí /start.")
        return ConversationHandler.END

    # ── Ver operarios ────────────────────────────────────────
    if accion == "cont_ver_op":
        operarios = get_operarios(cont["id"])
        botones   = []
        if operarios:
            lineas = ["👷 *Mis operarios*\n"]
            for op in operarios:
                icono = "✅" if op.get("telegram_id") else "⏳"
                lineas.append(f"{icono} {op['nombre']}")
                botones.append([InlineKeyboardButton(
                    f"{icono} {op['nombre']}",
                    callback_data=f"op_detalle_{op['id']}"
                )])
        else:
            lineas = ["No tenés operarios registrados todavía."]
        botones.append([InlineKeyboardButton("➕ Agregar operario", callback_data="cont_add_op")])
        botones.append([InlineKeyboardButton("⬅️ Volver",           callback_data="cont_volver")])
        await query.edit_message_text(
            "\n".join(lineas) if operarios else lineas[0],
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(botones)
        )
        return ConversationHandler.END

    # ── Ver clientes ─────────────────────────────────────────
    elif accion == "cont_ver_cli":
        clientes = get_clientes(cont["id"])
        botones  = []
        if clientes:
            lineas = ["👤 *Mis clientes*\n"]
            for cli in clientes:
                icono = "✅" if cli.get("telegram_id") else "⏳"
                lineas.append(f"{icono} {cli['nombre']} {cli['apellido']}")
                botones.append([InlineKeyboardButton(
                    f"{icono} {cli['nombre']} {cli['apellido']}",
                    callback_data=f"cli_detalle_{cli['id']}"
                )])
        else:
            lineas = ["No tenés clientes registrados todavía."]
        botones.append([InlineKeyboardButton("➕ Agregar cliente", callback_data="cont_add_cli")])
        botones.append([InlineKeyboardButton("⬅️ Volver",          callback_data="cont_volver")])
        await query.edit_message_text(
            "\n".join(lineas) if clientes else lineas[0],
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(botones)
        )
        return ConversationHandler.END

    # ── Detalle operario ─────────────────────────────────────
    elif accion.startswith("op_detalle_"):
        op_id = int(accion.replace("op_detalle_", ""))
        r     = supabase.table("usuarios").select("*").eq("id", op_id).execute()
        if not r.data:
            await query.edit_message_text("No se encontró el operario.")
            return ConversationHandler.END
        op      = r.data[0]
        icono   = "✅ Activo" if op.get("telegram_id") else "⏳ Pendiente de alta"
        botones = []
        if not op.get("telegram_id") and op.get("codigo_acceso"):
            botones.append([InlineKeyboardButton(
                f"🔑 Ver código: {op['codigo_acceso']}",
                callback_data=f"op_vercodigo_{op_id}"
            )])
        botones.append([InlineKeyboardButton("✏️ Modificar nombre",  callback_data=f"op_editar_{op_id}")])
        botones.append([InlineKeyboardButton("🗑️ Eliminar operario", callback_data=f"op_eliminar_{op_id}")])
        botones.append([InlineKeyboardButton("⬅️ Volver",            callback_data="cont_ver_op")])
        await query.edit_message_text(
            f"👷 *{op['nombre']}*\nEstado: {icono}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(botones)
        )
        return ConversationHandler.END

    # ── Detalle cliente ──────────────────────────────────────
    elif accion.startswith("cli_detalle_"):
        cli_id = int(accion.replace("cli_detalle_", ""))
        r      = supabase.table("clientes").select("*").eq("id", cli_id).execute()
        if not r.data:
            await query.edit_message_text("No se encontró el cliente.")
            return ConversationHandler.END
        cli     = r.data[0]
        icono   = "✅ Activo" if cli.get("telegram_id") else "⏳ Pendiente de alta"
        botones = []
        if not cli.get("telegram_id") and cli.get("codigo_acceso"):
            botones.append([InlineKeyboardButton(
                f"🔑 Ver código: {cli['codigo_acceso']}",
                callback_data=f"cli_vercodigo_{cli_id}"
            )])
        botones.append([InlineKeyboardButton("✏️ Modificar nombre", callback_data=f"cli_editar_{cli_id}")])
        botones.append([InlineKeyboardButton("🗑️ Eliminar cliente", callback_data=f"cli_eliminar_{cli_id}")])
        botones.append([InlineKeyboardButton("⬅️ Volver",           callback_data="cont_ver_cli")])
        await query.edit_message_text(
            f"👤 *{cli['nombre']} {cli['apellido']}*\nEstado: {icono}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(botones)
        )
        return ConversationHandler.END

    # ── Ver código ───────────────────────────────────────────
    elif accion.startswith("op_vercodigo_"):
        op_id = int(accion.replace("op_vercodigo_", ""))
        r     = supabase.table("usuarios").select("nombre,codigo_acceso").eq("id", op_id).execute()
        if r.data:
            await query.answer(f"Código de {r.data[0]['nombre']}: {r.data[0]['codigo_acceso']}", show_alert=True)
        return ConversationHandler.END

    elif accion.startswith("cli_vercodigo_"):
        cli_id = int(accion.replace("cli_vercodigo_", ""))
        r      = supabase.table("clientes").select("nombre,apellido,codigo_acceso").eq("id", cli_id).execute()
        if r.data:
            c = r.data[0]
            await query.answer(f"Código de {c['nombre']} {c['apellido']}: {c['codigo_acceso']}", show_alert=True)
        return ConversationHandler.END

    # ── Eliminar operario ────────────────────────────────────
    elif accion.startswith("op_eliminar_"):
        op_id = int(accion.replace("op_eliminar_", ""))
        r     = supabase.table("usuarios").select("nombre").eq("id", op_id).execute()
        nombre = r.data[0]["nombre"] if r.data else "este operario"
        teclado = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Sí, eliminar",  callback_data=f"op_confirmar_eliminar_{op_id}")],
            [InlineKeyboardButton("❌ Cancelar",       callback_data=f"op_detalle_{op_id}")],
        ])
        await query.edit_message_text(
            f"¿Confirmar eliminación de *{nombre}*?\nPierden el acceso al bot.",
            parse_mode="Markdown",
            reply_markup=teclado
        )
        return ConversationHandler.END

    elif accion.startswith("op_confirmar_eliminar_"):
        op_id = int(accion.replace("op_confirmar_eliminar_", ""))
        r     = supabase.table("usuarios").select("nombre").eq("id", op_id).execute()
        nombre = r.data[0]["nombre"] if r.data else ""
        supabase.table("usuarios").delete().eq("id", op_id).execute()
        await query.edit_message_text(
            f"✅ Operario *{nombre}* eliminado.",
            parse_mode="Markdown",
            reply_markup=teclado_menu_contratista(cont["id"], uid)
        )
        return ConversationHandler.END

    # ── Eliminar cliente ─────────────────────────────────────
    elif accion.startswith("cli_eliminar_"):
        cli_id = int(accion.replace("cli_eliminar_", ""))
        r      = supabase.table("clientes").select("nombre,apellido").eq("id", cli_id).execute()
        nombre = f"{r.data[0]['nombre']} {r.data[0]['apellido']}" if r.data else "este cliente"
        teclado = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Sí, eliminar", callback_data=f"cli_confirmar_eliminar_{cli_id}")],
            [InlineKeyboardButton("❌ Cancelar",      callback_data=f"cli_detalle_{cli_id}")],
        ])
        await query.edit_message_text(
            f"¿Confirmar eliminación de *{nombre}*?\nPierden el acceso al bot.",
            parse_mode="Markdown",
            reply_markup=teclado
        )
        return ConversationHandler.END

    elif accion.startswith("cli_confirmar_eliminar_"):
        cli_id = int(accion.replace("cli_confirmar_eliminar_", ""))
        r      = supabase.table("clientes").select("nombre,apellido").eq("id", cli_id).execute()
        nombre = f"{r.data[0]['nombre']} {r.data[0]['apellido']}" if r.data else ""
        supabase.table("clientes").delete().eq("id", cli_id).execute()
        await query.edit_message_text(
            f"✅ Cliente *{nombre}* eliminado.",
            parse_mode="Markdown",
            reply_markup=teclado_menu_contratista(cont["id"], uid)
        )
        return ConversationHandler.END

    # ── Agregar ──────────────────────────────────────────────
    elif accion.startswith("op_editar_"):
        op_id = int(accion.replace("op_editar_", ""))
        context.user_data["editando_op_id"] = op_id
        context.user_data["contratista_id"] = cont["id"]
        await query.edit_message_text("¿Cuál es el nuevo nombre del operario?")
        return ADD_OP_NOMBRE

    elif accion.startswith("cli_editar_"):
        cli_id = int(accion.replace("cli_editar_", ""))
        context.user_data["editando_cli_id"] = cli_id
        context.user_data["contratista_id"]  = cont["id"]
        await query.edit_message_text("¿Cuál es el nuevo nombre del cliente?")
        return ADD_CLI_NOMBRE
  
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
    nombre         = update.message.text.strip()
    contratista_id = context.user_data["contratista_id"]
    uid            = str(update.effective_user.id)

    if "editando_op_id" in context.user_data:
        op_id = context.user_data.pop("editando_op_id")
        supabase.table("usuarios").update({"nombre": nombre.split()[0]}).eq("id", op_id).execute()
        await update.message.reply_text(
            f"✅ Nombre actualizado a *{nombre}*.",
            parse_mode="Markdown",
            reply_markup=teclado_menu_contratista(contratista_id, uid)
        )
        return ConversationHandler.END

    context.user_data["nuevo_nombre"] = nombre
    teclado = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Sí, soy yo",         callback_data="op_soy_yo")],
        [InlineKeyboardButton("❌ No, es otra persona", callback_data="op_otro")],
    ])
    await update.message.reply_text(
        f"¿El operario *{nombre}* sos vos mismo?",
        parse_mode="Markdown", reply_markup=teclado
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
        r = supabase.table("usuarios").select("*").eq("telegram_id", uid).eq("contratista_id", contratista_id).execute()
        if r.data:
            await query.edit_message_text(
                "Ya estás registrado como operario.",
                reply_markup=teclado_menu_contratista(contratista_id, uid)
            )
            return ConversationHandler.END
        supabase.table("usuarios").insert({
            "nombre": partes[0], "rol": "operario",
            "telegram_id": uid, "contratista_id": contratista_id, "activo": True,
        }).execute()
        await query.edit_message_text(
            "✅ Quedaste registrado como operario.",
            reply_markup=teclado_menu_contratista(contratista_id, uid)
        )
    else:
        codigo = generar_codigo()
        supabase.table("usuarios").insert({
            "nombre": partes[0], "rol": "operario",
            "codigo_acceso": codigo, "contratista_id": contratista_id, "activo": True,
        }).execute()
        await query.edit_message_text(
            f"✅ Operario *{nombre}* creado.\n\nCódigo de acceso: *{codigo}*\nCompartíselo para que ingrese al bot.",
            parse_mode="Markdown",
            reply_markup=teclado_menu_contratista(contratista_id, uid)
        )
    return ConversationHandler.END

# ── Agregar cliente ──────────────────────────────────────────
async def add_cli_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nombre         = update.message.text.strip()
    contratista_id = context.user_data["contratista_id"]
    uid            = str(update.effective_user.id)

    if "editando_cli_id" in context.user_data:
        cli_id = context.user_data.pop("editando_cli_id")
        partes  = nombre.split()
        supabase.table("clientes").update({
            "nombre":   partes[0],
            "apellido": " ".join(partes[1:]) if len(partes) > 1 else ""
        }).eq("id", cli_id).execute()
        await update.message.reply_text(
            f"✅ Nombre actualizado a *{nombre}*.",
            parse_mode="Markdown",
            reply_markup=teclado_menu_contratista(contratista_id, uid)
        )
        return ConversationHandler.END

    context.user_data["nuevo_nombre"] = nombre
    teclado = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Sí, soy yo",         callback_data="cli_soy_yo")],
        [InlineKeyboardButton("❌ No, es otra persona", callback_data="cli_otro")],
    ])
    await update.message.reply_text(
        f"¿El cliente *{nombre}* sos vos mismo?",
        parse_mode="Markdown", reply_markup=teclado
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
            "nombre": nombre_p, "apellido": apellido_p,
            "telegram_id": uid, "contratista_id": contratista_id,
        }).execute()
        await query.edit_message_text(
            "✅ Quedaste registrado como cliente.",
            reply_markup=teclado_menu_contratista(contratista_id, uid)
        )
    else:
        codigo = generar_codigo()
        supabase.table("clientes").insert({
            "nombre": nombre_p, "apellido": apellido_p,
            "codigo_acceso": codigo, "contratista_id": contratista_id,
        }).execute()
        await query.edit_message_text(
            f"✅ Cliente *{nombre}* creado.\n\nCódigo de acceso: *{codigo}*\nCompartíselo para que ingrese al bot.",
            parse_mode="Markdown",
            reply_markup=teclado_menu_contratista(contratista_id, uid)
        )
    return ConversationHandler.END

# ── Handler mensajes libres ──────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)

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
            f"Hola {cli['nombre']} {cli['apellido']}! Sos cliente de *{cont_nombre}*.\n"
            "Próximamente podrás consultar tus datos desde acá.",
            parse_mode="Markdown"
        )
        return

    # No registrado → pedir código
    await update.message.reply_text(
        "No tenés permisos para acceder.\n\n"
        "Si sos contratista escribí /start.\n"
        "Si sos operario o cliente, ingresá el código que te dio tu contratista:"
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
            REG_ROL:          [CallbackQueryHandler(elegir_rol, pattern="^rol_")],
            REG_NOMBRE:       [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_nombre_contratista)],
            INGRESAR_CODIGO:  [MessageHandler(filters.TEXT & ~filters.COMMAND, ingresar_codigo)],
            CONFIRMAR_NOMBRE: [CallbackQueryHandler(confirmar_nombre, pattern="^nombre_")],
            CORREGIR_NOMBRE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, corregir_nombre)],
        },
        fallbacks=[CommandHandler("start", cmd_start)],
        per_message=False
    )

    menu_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(menu_contratista_callback, pattern="^(cont_|op_|cli_)")],
        states={
            ADD_OP_NOMBRE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, add_op_nombre)],
            ADD_OP_SOY_YO:  [CallbackQueryHandler(add_op_soy_yo,  pattern="^op_")],
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
