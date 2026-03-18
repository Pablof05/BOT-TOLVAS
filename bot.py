import os, re, logging
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
 LOTE_CLIENTE, LOTE_CAMPO, LOTE_LOTE,
 NUEVO_CLIENTE_NOMBRE, NUEVO_CAMPO_NOMBRE, NUEVO_LOTE_NOMBRE,
 CAMION_CHASIS, CAMION_ACOPLADO, CAMION_CAPACIDAD,
 NUEVO_CAMION_CHASIS, NUEVO_CAMION_ACOPLADO, NUEVO_CAMION_CAPACIDAD,
 DESCARGA_KG) = range(14)

def ahora():
    return datetime.now(ARG)

def get_usuario(telegram_id: str):
    r = supabase.table("usuarios").select("*").eq("telegram_id", telegram_id).execute()
    return r.data[0] if r.data else None

def get_sesion(chat_id: str):
    r = supabase.table("sesion_activa").select(
        "*, clientes(nombre,apellido), campos(nombre), lotes(nombre)"
    ).eq("chat_id", chat_id).execute()
    return r.data[0] if r.data else None

def get_destinos_abiertos(lote_id: int, chat_id: str):
    destinos = []
    r = supabase.table("descargas").select(
        "camion_id, kg, camiones(patente_chasis,patente_acoplado,capacidad_kg)"
    ).eq("chat_id", chat_id).eq("destino", "camion").execute()
    camiones = {}
    for d in r.data or []:
        cid = d["camion_id"]
        if not cid: continue
        if cid not in camiones:
            c = d.get("camiones") or {}
            camiones[cid] = {"id": cid, "chasis": c.get("patente_chasis","?"), "acoplado": c.get("patente_acoplado","?"), "capacidad": c.get("capacidad_kg"), "kg": 0}
        camiones[cid]["kg"] += float(d["kg"])
    for c in camiones.values():
        if c["capacidad"] is None or c["kg"] < c["capacidad"]:
            faltan = (c["capacidad"] - c["kg"]) if c["capacidad"] else None
            destinos.append({"tipo": "camion", "id": c["id"], "label": f"🚛 {c['chasis']} / {c['acoplado']}", "kg": c["kg"], "capacidad": c["capacidad"], "faltan": faltan})
    r = supabase.table("silobolsas").select("*").eq("lote_id", lote_id).execute()
    for s in r.data or []:
        kg_silo = sum(float(d["kg"]) for d in (supabase.table("descargas").select("kg").eq("silobolsa_id", s["id"]).execute().data or []))
        destinos.append({"tipo": "silo", "id": s["id"], "label": f"🌾 Silobolsa #{s['numero']}", "kg": kg_silo, "capacidad": None, "faltan": None})
    return destinos

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

def armar_confirmacion(sesion, kg, destino_info, acumulado_antes):
    cliente_obj  = sesion.get("clientes") or {}
    cliente_str  = f"{cliente_obj.get('nombre','')} {cliente_obj.get('apellido','')}".strip() or "—"
    campo_str    = (sesion.get("campos") or {}).get("nombre", "—")
    lote_str     = (sesion.get("lotes")  or {}).get("nombre", "—")
    acumulado    = acumulado_antes + kg
    if destino_info["tipo"] == "camion":
        capacidad = destino_info.get("capacidad")
        lineas = [
            f"✅ *{cliente_str} / {campo_str} / {lote_str}*",
            f"🚛 {destino_info['label'].replace('🚛 ','')}",
            f"Esta carga:  *{kg:,.0f} kg*",
            f"Acumulado:   *{acumulado:,.0f} kg*" + (f" / {capacidad:,.0f} kg" if capacidad else ""),
        ]
        if capacidad:
            faltan = max(capacidad - acumulado, 0)
            lineas.append(barra(acumulado, capacidad))
            if faltan == 0:
                lineas.append("✅ Camión completo")
            elif acumulado / capacidad >= 0.85:
                lineas.append(f"Faltan: *{faltan:,.0f} kg* ⚠️ casi lleno")
            else:
                lineas.append(f"Faltan: *{faltan:,.0f} kg*")
    else:
        lineas = [
            f"✅ *{cliente_str} / {campo_str} / {lote_str}*",
            f"{destino_info['label']}",
            f"Esta carga:  *{kg:,.0f} kg*",
            f"Acumulado:   *{acumulado:,.0f} kg*",
        ]
    return "\n".join(lineas)

def guardar_descarga(sesion, kg, usuario, ts, destino_info):
    data = {
        "kg":           kg,
        "destino":      destino_info["tipo"],
        "camion_id":    destino_info["id"] if destino_info["tipo"] == "camion" else None,
        "silobolsa_id": destino_info["id"] if destino_info["tipo"] == "silo"   else None,
        "lote_id":      sesion.get("lote_id"),
        "campo_id":     sesion.get("campo_id"),
        "cliente_id":   sesion.get("cliente_id"),
        "tolva":        sesion.get("chat_id"),
        "operario_id":  usuario["id"] if usuario else None,
        "chat_id":      sesion["chat_id"],
        "created_at":   ts.isoformat(),
    }
    supabase.table("descargas").insert(data).execute()

def teclado_destinos(destinos, kg, incluir_nuevo=True):
    botones = []
    for d in destinos:
        faltan_str = f" — faltan {d['faltan']:,.0f} kg" if d.get("faltan") else ""
        botones.append([InlineKeyboardButton(f"{d['label']}{faltan_str}", callback_data=f"dst_{d['tipo']}_{d['id']}_{kg}")])
    if incluir_nuevo:
        botones.append([InlineKeyboardButton("🚛 Nuevo camión",    callback_data=f"dst_nuevo_camion_{kg}")])
        botones.append([InlineKeyboardButton("🌾 Nuevo silobolsa", callback_data=f"dst_nuevo_silo_{kg}")])
    return InlineKeyboardMarkup(botones)

def teclado_inicio(rol: str, sesion=None):
    if rol in ("operario", "encargado"):
        botones = [
            [InlineKeyboardButton("📊 Resumen",           callback_data="menu_resumen"),
             InlineKeyboardButton("📋 Descargas de hoy",  callback_data="menu_descargas")],
            [InlineKeyboardButton("🚛 Camiones activos",  callback_data="menu_camiones"),
             InlineKeyboardButton("🌾 Silos activos",     callback_data="menu_silos")],
            [InlineKeyboardButton("➕ Registrar descarga", callback_data="menu_descarga")],
            [InlineKeyboardButton("🔄 Cambiar lote",      callback_data="menu_nuevolote"),
             InlineKeyboardButton("🚛 Nuevo camión",      callback_data="menu_nuevocamion")],
            [InlineKeyboardButton("🌾 Nuevo silobolsa",   callback_data="menu_nuevosilo")],
        ]
    else:
        botones = [
            [InlineKeyboardButton("📊 Mi resumen",           callback_data="menu_resumen"),
             InlineKeyboardButton("📋 Mis descargas de hoy", callback_data="menu_descargas")],
            [InlineKeyboardButton("🌾 Mis silobolsas",       callback_data="menu_silos")],
        ]
    return InlineKeyboardMarkup(botones)

def teclado_clientes():
    r = supabase.table("clientes").select("*").order("apellido").execute()
    botones = []
    for c in r.data or []:
        botones.append([InlineKeyboardButton(f"{c['nombre']} {c['apellido']}", callback_data=f"cli_{c['id']}")])
    botones.append([InlineKeyboardButton("➕ Nuevo cliente", callback_data="cli_nuevo")])
    return InlineKeyboardMarkup(botones), r.data or []

def teclado_campos(cliente_id: int):
    r = supabase.table("campos").select("*").eq("cliente_id", cliente_id).order("nombre").execute()
    botones = []
    for c in r.data or []:
        botones.append([InlineKeyboardButton(c["nombre"], callback_data=f"campo_{c['id']}")])
    botones.append([InlineKeyboardButton("➕ Nuevo campo", callback_data="campo_nuevo")])
    return InlineKeyboardMarkup(botones), r.data or []

def teclado_lotes(campo_id: int):
    r = supabase.table("lotes").select("*").eq("campo_id", campo_id).order("nombre").execute()
    botones = []
    for l in r.data or []:
        botones.append([InlineKeyboardButton(l["nombre"], callback_data=f"lote_{l['id']}")])
    botones.append([InlineKeyboardButton("➕ Nuevo lote", callback_data="lote_nuevo")])
    return InlineKeyboardMarkup(botones), r.data or []

def nombre_similar(nombre: str, lista: list) -> list:
    nombre_lower = nombre.lower()
    similares    = []
    for item in lista:
        n = f"{item.get('nombre','')} {item.get('apellido','')}".strip().lower()
        palabras = [p for p in nombre_lower.split() if len(p) > 2]
        if any(p in n for p in palabras):
            similares.append(item)
    return similares

def teclado_roles():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👷 Operario de tolva",      callback_data="rol_operario")],
        [InlineKeyboardButton("👤 Cliente / dueño granos", callback_data="rol_cliente")],
        [InlineKeyboardButton("⚙️ Encargado del equipo",   callback_data="rol_encargado")],
    ])

# ── Herramientas Claude ──────────────────────────────────────
def tool_descargas_hoy(chat_id: str, cliente_id: int = None) -> str:
    desde = ahora().replace(hour=0, minute=0, second=0, microsecond=0)
    q = (supabase.table("descargas")
         .select("kg, destino, created_at, camiones(patente_chasis,patente_acoplado), silobolsas(numero), lotes(nombre)")
         .eq("chat_id", chat_id).gte("created_at", desde.isoformat()).order("created_at"))
    if cliente_id: q = q.eq("cliente_id", cliente_id)
    r = q.execute()
    if not r.data: return "No hay descargas hoy."
    lineas = [f"📋 *Descargas de hoy* ({len(r.data)})\n"]
    total  = 0
    for d in r.data:
        hora = datetime.fromisoformat(d["created_at"]).astimezone(ARG).strftime("%H:%M")
        kg   = float(d["kg"]); total += kg
        dest = f"🚛 {(d.get('camiones') or {}).get('patente_chasis','')} / {(d.get('camiones') or {}).get('patente_acoplado','')}" if d["destino"] == "camion" else f"🌾 Silo #{(d.get('silobolsas') or {}).get('numero','?')}"
        lote = (d.get("lotes") or {}).get("nombre","")
        lineas.append(f"{hora} — {dest} — *{kg:,.0f} kg*" + (f" ({lote})" if lote else ""))
    lineas.append(f"\nTotal: *{total:,.0f} kg*")
    return "\n".join(lineas)

def tool_camiones_activos(chat_id: str) -> str:
    r = (supabase.table("descargas").select("camion_id, kg, camiones(patente_chasis,patente_acoplado,capacidad_kg)")
         .eq("chat_id", chat_id).eq("destino", "camion").execute())
    if not r.data: return "No hay camiones activos."
    camiones = {}
    for d in r.data:
        cid = d["camion_id"]; c = d.get("camiones") or {}
        if cid not in camiones:
            camiones[cid] = {"chasis": c.get("patente_chasis","?"), "acoplado": c.get("patente_acoplado","?"), "capacidad": c.get("capacidad_kg"), "kg": 0}
        camiones[cid]["kg"] += float(d["kg"])
    activos = {cid: v for cid, v in camiones.items() if v["capacidad"] is None or v["kg"] < v["capacidad"]}
    if not activos: return "No hay camiones con espacio disponible."
    lineas = [f"🚛 *Camiones activos* ({len(activos)})\n"]
    for v in activos.values():
        faltan_str = f" — faltan *{v['capacidad']-v['kg']:,.0f} kg*" if v["capacidad"] else ""
        lineas.append(f"{v['chasis']} / {v['acoplado']} — *{v['kg']:,.0f} kg*{faltan_str}")
    return "\n".join(lineas)

def tool_silos_activos(chat_id: str, lote_id: int = None, cliente_id: int = None) -> str:
    q = supabase.table("silobolsas").select("*, lotes(nombre, campos(nombre))")
    if lote_id: q = q.eq("lote_id", lote_id)
    r = q.execute()
    if not r.data: return "No hay silobolsas registrados."
    lineas = ["🌾 *Silobolsas*\n"]
    for s in r.data:
        kg = sum(float(d["kg"]) for d in (supabase.table("descargas").select("kg").eq("silobolsa_id", s["id"]).execute().data or []))
        lote  = (s.get("lotes") or {}).get("nombre","?")
        lineas.append(f"Silo #{s['numero']} ({lote}) — *{kg:,.0f} kg*")
    return "\n".join(lineas)

def tool_resumen_periodo(chat_id: str, periodo: str, cliente_id: int = None) -> str:
    ahora_ts = ahora()
    if periodo == "mes":
        desde = ahora_ts.replace(day=1, hour=0, minute=0, second=0, microsecond=0); titulo = f"Mes {ahora_ts.strftime('%B %Y')}"
    elif periodo == "semana":
        desde = ahora_ts - timedelta(days=7); titulo = "Últimos 7 días"
    else:
        desde = ahora_ts.replace(hour=0, minute=0, second=0, microsecond=0); titulo = f"Hoy {ahora_ts.strftime('%d/%m/%Y')}"
    q = supabase.table("descargas").select("kg, destino, camion_id, silobolsa_id, cliente_id, clientes(nombre,apellido), lotes(nombre)").gte("created_at", desde.isoformat())
    if cliente_id: q = q.eq("cliente_id", cliente_id)
    res = q.order("created_at", desc=True).execute()
    if not res.data: return f"Sin registros para {titulo}."
    total_kg = sum(float(r["kg"]) for r in res.data)
    lineas   = [f"📊 *{titulo}*\n",
                f"Total: *{total_kg:,.0f} kg*",
                f"Camiones: {len({r['camion_id'] for r in res.data if r['camion_id']})}  |  Silobolsas: {len({r['silobolsa_id'] for r in res.data if r['silobolsa_id']})}",
                f"Descargas: {len(res.data)}\n"]
    clientes = {}
    for r in res.data:
        c = r.get("clientes"); nombre = f"{c['nombre']} {c['apellido']}" if c else "Sin cliente"
        clientes[nombre] = clientes.get(nombre, 0) + float(r["kg"])
    for nombre, kg in sorted(clientes.items()):
        lineas.append(f"👤 *{nombre}*: {kg:,.0f} kg")
    return "\n".join(lineas)

def tool_listar_clientes() -> str:
    r = supabase.table("clientes").select("*").order("apellido").execute()
    if not r.data: return "No hay clientes registrados."
    return "👤 *Clientes registrados*\n\n" + "\n".join(f"{c['nombre']} {c['apellido']}" for c in r.data)

def tool_estado_camion(patente: str, chat_id: str) -> str:
    patente = patente.upper().replace(" ", "")
    r = supabase.table("camiones").select("*").eq("patente_chasis", patente).execute()
    if not r.data: r = supabase.table("camiones").select("*").eq("patente_acoplado", patente).execute()
    if not r.data: return f"No encontré el camión {patente}."
    camion    = r.data[0]
    acumulado = sum(float(d["kg"]) for d in (supabase.table("descargas").select("kg").eq("camion_id", camion["id"]).eq("chat_id", chat_id).execute().data or []))
    capacidad = camion.get("capacidad_kg")
    lineas    = [f"🚛 *{camion['patente_chasis']} / {camion['patente_acoplado']}*", f"Acumulado: *{acumulado:,.0f} kg*"]
    if capacidad:
        faltan = max(capacidad - acumulado, 0)
        lineas.append(barra(acumulado, capacidad))
        lineas.append(f"Capacidad: {capacidad:,.0f} kg — Faltan: {faltan:,.0f} kg")
    return "\n".join(lineas)

TOOLS = [
    {"name": "descargas_hoy",    "description": "Muestra todas las descargas de hoy", "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "camiones_activos", "description": "Lista camiones activos con kg y espacio disponible", "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "silos_activos",    "description": "Lista silobolsas con kg acumulados", "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "listar_clientes",  "description": "Lista todos los clientes registrados", "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "resumen_periodo",  "description": "Resumen de kg por período",
     "input_schema": {"type": "object", "properties": {"periodo": {"type": "string", "enum": ["hoy", "semana", "mes"]}}, "required": ["periodo"]}},
    {"name": "estado_camion",    "description": "Estado de un camión específico",
     "input_schema": {"type": "object", "properties": {"patente": {"type": "string"}}, "required": ["patente"]}},
]

def consultar_claude_con_tools(mensaje: str, sesion, usuario, chat_id: str) -> str:
    sesion_str = "Sin sesión activa."
    if sesion and sesion.get("lote_id"):
        cliente_obj = sesion.get("clientes") or {}
        sesion_str  = (f"Cliente: {cliente_obj.get('nombre','')} {cliente_obj.get('apellido','')}, "
                       f"Campo: {(sesion.get('campos') or {}).get('nombre','')}, "
                       f"Lote: {(sesion.get('lotes') or {}).get('nombre','')}")
    system = (
        "Sos el asistente de un sistema de tolvas agrícolas argentino. "
        "Respondé en español, de forma directa y profesional, sin tuteos informales ni expresiones coloquiales. "
        "Usá un tono claro y conciso, sin bullets ni listas. "
        "Cuando necesites datos reales usá las herramientas — nunca inventes datos. "
        f"Sesión activa: {sesion_str}. Usuario: {usuario['nombre']} ({usuario['rol']})."
    )
    messages = [{"role": "user", "content": mensaje}]
    try:
        resp = claude.messages.create(model="claude-haiku-4-5", max_tokens=512, system=system, tools=TOOLS, messages=messages)
        while resp.stop_reason == "tool_use":
            tool_use = next(b for b in resp.content if b.type == "tool_use")
            inp      = tool_use.input
            cliente_id = usuario.get("cliente_id") if usuario and usuario["rol"] == "cliente" else None
            if tool_use.name == "descargas_hoy":       result = tool_descargas_hoy(chat_id, cliente_id)
            elif tool_use.name == "camiones_activos":  result = tool_camiones_activos(chat_id)
            elif tool_use.name == "silos_activos":     result = tool_silos_activos(chat_id, cliente_id=cliente_id)
            elif tool_use.name == "listar_clientes":   result = tool_listar_clientes()
            elif tool_use.name == "resumen_periodo":   result = tool_resumen_periodo(chat_id, inp.get("periodo","hoy"), cliente_id)
            elif tool_use.name == "estado_camion":     result = tool_estado_camion(inp.get("patente",""), chat_id)
            else:                                      result = "Herramienta no disponible."
            messages = messages + [
                {"role": "assistant", "content": resp.content},
                {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tool_use.id, "content": result}]}
            ]
            resp = claude.messages.create(model="claude-haiku-4-5", max_tokens=512, system=system, tools=TOOLS, messages=messages)
        return next((b.text for b in resp.content if hasattr(b, "text")), "").strip()
    except Exception as e:
        logging.error(f"Error Claude: {e}")
        return "No pude procesar eso. Intentá de nuevo."

# ── Menú inicio ──────────────────────────────────────────────
async def mostrar_menu(update_or_msg, usuario, sesion=None, texto="¿Qué querés hacer?"):
    teclado = teclado_inicio(usuario["rol"], sesion)
    if hasattr(update_or_msg, 'reply_text'):
        await update_or_msg.reply_text(texto, reply_markup=teclado)
    else:
        await update_or_msg.message.reply_text(texto, reply_markup=teclado)

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    chat_id = str(update.effective_chat.id)
    uid     = str(update.effective_user.id)
    usuario = get_usuario(uid)
    sesion  = get_sesion(chat_id)
    data    = query.data.replace("menu_", "")

    if data == "resumen":
        teclado = InlineKeyboardMarkup([
            [InlineKeyboardButton("📅 Hoy",          callback_data="res_hoy"),
             InlineKeyboardButton("📆 Esta semana",   callback_data="res_semana"),
             InlineKeyboardButton("🗓 Este mes",      callback_data="res_mes")],
            [InlineKeyboardButton("🚛 Por camión",    callback_data="res_tipo_camion"),
             InlineKeyboardButton("🌾 Por silobolsa", callback_data="res_tipo_silo")],
            [InlineKeyboardButton("👤 Por cliente",   callback_data="res_tipo_cliente"),
             InlineKeyboardButton("🌱 Por lote",      callback_data="res_tipo_lote")],
        ])
        await query.edit_message_text("¿Qué resumen querés ver?", reply_markup=teclado)

    elif data == "descargas":
        cliente_id = usuario.get("cliente_id") if usuario["rol"] == "cliente" else None
        await query.edit_message_text(tool_descargas_hoy(chat_id, cliente_id), parse_mode="Markdown")

    elif data == "camiones":
        await query.edit_message_text(tool_camiones_activos(chat_id), parse_mode="Markdown")

    elif data == "silos":
        lote_id    = sesion.get("lote_id") if sesion else None
        cliente_id = usuario.get("cliente_id") if usuario["rol"] == "cliente" else None
        await query.edit_message_text(tool_silos_activos(chat_id, lote_id, cliente_id), parse_mode="Markdown")

    elif data == "descarga":
        if not sesion or not sesion.get("lote_id"):
            await query.edit_message_text("No hay sesión activa. Usá /nuevolote primero.")
            return
        destinos = get_destinos_abiertos(sesion["lote_id"], chat_id)
        context.user_data["esperando_kg_para_destino"] = True
        if destinos:
            teclado = teclado_destinos(destinos, "?", incluir_nuevo=True)
            await query.edit_message_text("¿A dónde va la descarga?", reply_markup=teclado)
        else:
            teclado = InlineKeyboardMarkup([
                [InlineKeyboardButton("🚛 Nuevo camión",    callback_data="dst_nuevo_camion_?")],
                [InlineKeyboardButton("🌾 Nuevo silobolsa", callback_data="dst_nuevo_silo_?")],
            ])
            await query.edit_message_text("¿A dónde va la descarga?", reply_markup=teclado)

    elif data == "nuevolote":
        await query.edit_message_text("Iniciando cambio de lote...")
        await cmd_nuevolote(update, context)

    elif data == "nuevocamion":
        await query.edit_message_text("Iniciando registro de camión...")
        await cmd_nuevocamion(update, context)

    elif data == "nuevosilo":
        await cmd_nuevosilo_desde_callback(query, chat_id, sesion)

async def cmd_nuevosilo_desde_callback(query, chat_id, sesion):
    if not sesion or not sesion.get("lote_id"):
        await query.edit_message_text("No hay sesión activa. Usá /nuevolote primero.")
        return
    lote_id = sesion["lote_id"]
    r       = supabase.table("silobolsas").select("numero").eq("lote_id", lote_id).order("numero", desc=True).execute()
    numero  = (r.data[0]["numero"] + 1) if r.data else 1
    supabase.table("silobolsas").insert({"numero": numero, "lote_id": lote_id}).execute()
    await query.edit_message_text(f"🌾 Silobolsa #{numero} abierto. Mandá las descargas.")

# ── /start y registro ────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if get_usuario(uid):
        u = get_usuario(uid)
        await update.message.reply_text(f"Hola {u['nombre']}!", parse_mode="Markdown")
        await mostrar_menu(update.message, u, get_sesion(str(update.effective_chat.id)))
        return ConversationHandler.END
    await update.message.reply_text("Hola! Bienvenido al bot de tolvas.\n\n¿Quién sos?", reply_markup=teclado_roles())
    return REGISTRO_NOMBRE

async def elegir_rol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    rol   = query.data.replace("rol_", "")
    context.user_data["rol"] = rol
    roles = {"operario": "Operario", "cliente": "Cliente", "encargado": "Encargado"}
    await query.edit_message_text(f"Elegiste: *{roles[rol]}*\n\n¿Cuál es tu nombre y apellido?", parse_mode="Markdown")
    return REGISTRO_NOMBRE

async def recibir_nombre_registro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nombre = update.message.text.strip()
    rol    = context.user_data.get("rol", "operario")
    uid    = str(update.effective_user.id)
    supabase.table("usuarios").insert({"telegram_id": uid, "nombre": nombre, "rol": rol, "activo": True}).execute()
    usuario = get_usuario(uid)
    await update.message.reply_text(f"✅ Bienvenido *{nombre}*! Quedaste registrado como *{rol}*.", parse_mode="Markdown")
    await mostrar_menu(update.message, usuario)
    return ConversationHandler.END

# ── /ayuda ───────────────────────────────────────────────────
async def cmd_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid     = str(update.effective_user.id)
    usuario = get_usuario(uid)
    if not usuario:
        await update.message.reply_text("Primero registrate con /start.")
        return
    await mostrar_menu(update.message, usuario, get_sesion(str(update.effective_chat.id)), "¿Qué necesitás?")

# ── /nuevolote ───────────────────────────────────────────────
async def cmd_nuevolote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid     = str(update.effective_user.id)
    usuario = get_usuario(uid)
    if not usuario or usuario["rol"] not in ("operario", "encargado"):
        if update.message:
            await update.message.reply_text("Solo operarios y encargados pueden hacer esto.")
        return ConversationHandler.END
    context.user_data.clear()
    teclado, clientes = teclado_clientes()
    msg = "¿Para qué cliente es esta cosecha?"
    if update.callback_query:
        await update.callback_query.message.reply_text(msg, reply_markup=teclado if clientes else None)
    else:
        await update.message.reply_text(msg, reply_markup=teclado if clientes else None)
    return LOTE_CLIENTE

async def lote_recibir_cliente_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto    = update.message.text.strip()
    r        = supabase.table("clientes").select("*").execute()
    similares = nombre_similar(texto, r.data or [])
    if similares and not any(f"{c['nombre']} {c['apellido']}".lower() == texto.lower() for c in similares):
        botones = [[InlineKeyboardButton(f"{c['nombre']} {c['apellido']}", callback_data=f"cli_{c['id']}")] for c in similares]
        botones.append([InlineKeyboardButton("➕ No, crear nuevo", callback_data=f"cli_nuevo_nombre_{texto}")])
        await update.message.reply_text(
            f"Encontré clientes similares a *{texto}* — ¿es alguno de estos?",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(botones)
        )
        return LOTE_CAMPO
    r2 = supabase.table("clientes").select("*").ilike("apellido", f"%{texto}%").execute()
    if not r2.data:
        r2 = supabase.table("clientes").select("*").ilike("nombre", f"%{texto}%").execute()
    if r2.data and len(r2.data) == 1:
        context.user_data["cliente_id"]  = r2.data[0]["id"]
        context.user_data["cliente_str"] = f"{r2.data[0]['nombre']} {r2.data[0]['apellido']}"
        teclado, _ = teclado_campos(r2.data[0]["id"])
        await update.message.reply_text(f"✅ *{context.user_data['cliente_str']}*\n\n¿En qué campo?", parse_mode="Markdown", reply_markup=teclado)
        return LOTE_CAMPO
    partes = texto.split()
    nuevo  = supabase.table("clientes").insert({"nombre": partes[0], "apellido": " ".join(partes[1:]) if len(partes) > 1 else ""}).execute()
    context.user_data["cliente_id"]  = nuevo.data[0]["id"]
    context.user_data["cliente_str"] = texto
    teclado, _ = teclado_campos(nuevo.data[0]["id"])
    await update.message.reply_text(f"Cliente *{texto}* creado.\n\n¿En qué campo?", parse_mode="Markdown", reply_markup=teclado)
    return LOTE_CAMPO

async def lote_elegir_cliente(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data  = query.data
    if data == "cli_nuevo":
        await query.edit_message_text("¿Nombre y apellido del nuevo cliente?")
        return NUEVO_CLIENTE_NOMBRE
    if data.startswith("cli_nuevo_nombre_"):
        nombre = data.replace("cli_nuevo_nombre_", "")
        partes = nombre.split()
        nuevo  = supabase.table("clientes").insert({"nombre": partes[0], "apellido": " ".join(partes[1:]) if len(partes) > 1 else ""}).execute()
        context.user_data["cliente_id"]  = nuevo.data[0]["id"]
        context.user_data["cliente_str"] = nombre
        teclado, _ = teclado_campos(nuevo.data[0]["id"])
        await query.edit_message_text(f"Cliente *{nombre}* creado.\n\n¿En qué campo?", parse_mode="Markdown", reply_markup=teclado)
        return LOTE_CAMPO
    cid = int(data.replace("cli_", ""))
    r   = supabase.table("clientes").select("*").eq("id", cid).execute()
    c   = r.data[0]
    context.user_data["cliente_id"]  = cid
    context.user_data["cliente_str"] = f"{c['nombre']} {c['apellido']}"
    teclado, _ = teclado_campos(cid)
    await query.edit_message_text(f"✅ *{context.user_data['cliente_str']}*\n\n¿En qué campo?", parse_mode="Markdown", reply_markup=teclado)
    return LOTE_CAMPO

async def nuevo_cliente_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto  = update.message.text.strip()
    partes = texto.split()
    nuevo  = supabase.table("clientes").insert({"nombre": partes[0], "apellido": " ".join(partes[1:]) if len(partes) > 1 else ""}).execute()
    context.user_data["cliente_id"]  = nuevo.data[0]["id"]
    context.user_data["cliente_str"] = texto
    teclado, _ = teclado_campos(nuevo.data[0]["id"])
    await update.message.reply_text(f"Cliente *{texto}* creado.\n\n¿En qué campo?", parse_mode="Markdown", reply_markup=teclado)
    return LOTE_CAMPO

async def lote_elegir_campo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data  = query.data
    if data == "campo_nuevo":
        await query.edit_message_text("¿Nombre del nuevo campo?")
        return NUEVO_CAMPO_NOMBRE
    campo_id = int(data.replace("campo_", ""))
    r        = supabase.table("campos").select("*").eq("id", campo_id).execute()
    context.user_data["campo_id"] = campo_id
    teclado, _ = teclado_lotes(campo_id)
    await query.edit_message_text(f"✅ Campo *{r.data[0]['nombre']}*\n\n¿En qué lote?", parse_mode="Markdown", reply_markup=teclado)
    return LOTE_LOTE

async def nuevo_campo_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto      = update.message.text.strip()
    cliente_id = context.user_data["cliente_id"]
    nuevo      = supabase.table("campos").insert({"nombre": texto, "cliente_id": cliente_id}).execute()
    context.user_data["campo_id"] = nuevo.data[0]["id"]
    teclado, _ = teclado_lotes(nuevo.data[0]["id"])
    await update.message.reply_text(f"Campo *{texto}* creado.\n\n¿En qué lote?", parse_mode="Markdown", reply_markup=teclado)
    return LOTE_LOTE

async def lote_elegir_lote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data  = query.data
    if data == "lote_nuevo":
        await query.edit_message_text("¿Nombre del nuevo lote?")
        return NUEVO_LOTE_NOMBRE
    lote_id = int(data.replace("lote_", ""))
    r       = supabase.table("lotes").select("*").eq("id", lote_id).execute()
    await _finalizar_sesion(update.effective_chat.id, lote_id, context, r.data[0]["nombre"], query)
    return ConversationHandler.END

async def nuevo_lote_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto    = update.message.text.strip()
    campo_id = context.user_data["campo_id"]
    r        = supabase.table("lotes").select("*").eq("campo_id", campo_id).ilike("nombre", f"%{texto}%").execute()
    lote_id  = r.data[0]["id"] if r.data else supabase.table("lotes").insert({"nombre": texto, "campo_id": campo_id}).execute().data[0]["id"]
    await _finalizar_sesion(update.effective_chat.id, lote_id, context, texto, update)
    return ConversationHandler.END

async def _finalizar_sesion(chat_id, lote_id, context, lote_nombre, update_or_query):
    chat_id_str = str(chat_id)
    supabase.table("sesion_activa").upsert({
        "chat_id":     chat_id_str,
        "cliente_id":  context.user_data["cliente_id"],
        "campo_id":    context.user_data["campo_id"],
        "lote_id":     lote_id,
        "iniciada_at": ahora().isoformat()
    }).execute()
    destinos = get_destinos_abiertos(lote_id, chat_id_str)
    if destinos:
        teclado = teclado_destinos(destinos, 0, incluir_nuevo=True)
        texto   = f"✅ Sesión iniciada: *{lote_nombre}*\n\nHay destinos abiertos para este lote:"
    else:
        teclado = None
        texto   = f"✅ Sesión iniciada: *{lote_nombre}*\n\nMandá las descargas cuando quieras."
    if hasattr(update_or_query, 'edit_message_text'):
        await update_or_query.edit_message_text(texto, parse_mode="Markdown", reply_markup=teclado)
    else:
        await update_or_query.message.reply_text(texto, parse_mode="Markdown", reply_markup=teclado)

# ── /nuevocamion ─────────────────────────────────────────────
async def cmd_nuevocamion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid     = str(update.effective_user.id)
    usuario = get_usuario(uid)
    if not usuario or usuario["rol"] not in ("operario", "encargado"):
        if update.message:
            await update.message.reply_text("Solo operarios y encargados pueden hacer esto.")
        return ConversationHandler.END
    context.user_data.pop("patente_chasis", None)
    context.user_data.pop("patente_acoplado", None)
    context.user_data.pop("kg_pendiente", None)
    msg = "¿Patente del *chasis*?"
    if update.callback_query:
        await update.callback_query.message.reply_text(msg, parse_mode="Markdown")
    else:
        await update.message.reply_text(msg, parse_mode="Markdown")
    return NUEVO_CAMION_CHASIS

async def nuevo_camion_chasis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["patente_chasis"] = re.sub(r'\s+', '', update.message.text.upper().strip())
    await update.message.reply_text("¿Patente del *acoplado*?", parse_mode="Markdown")
    return NUEVO_CAMION_ACOPLADO

async def nuevo_camion_acoplado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["patente_acoplado"] = re.sub(r'\s+', '', update.message.text.upper().strip())
    await update.message.reply_text("¿Capacidad en kg? (ej: `30000`) — Si no sabés escribí *0*", parse_mode="Markdown")
    return NUEVO_CAMION_CAPACIDAD

async def nuevo_camion_capacidad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    try:
        cap = float(update.message.text.strip().replace('.','').replace(',','.'))
    except ValueError:
        cap = 0
    chasis   = context.user_data["patente_chasis"]
    acoplado = context.user_data["patente_acoplado"]
    kg_pend  = context.user_data.get("kg_pendiente", 0)
    r = supabase.table("camiones").select("*").eq("patente_chasis", chasis).eq("patente_acoplado", acoplado).execute()
    if r.data:
        camion_id = r.data[0]["id"]
        if cap > 0: supabase.table("camiones").update({"capacidad_kg": cap}).eq("id", camion_id).execute()
    else:
        nuevo     = supabase.table("camiones").insert({"patente_chasis": chasis, "patente_acoplado": acoplado, "capacidad_kg": cap if cap > 0 else None}).execute()
        camion_id = nuevo.data[0]["id"]
    sesion       = get_sesion(chat_id)
    destino_info = {"tipo": "camion", "id": camion_id, "label": f"🚛 {chasis} / {acoplado}", "capacidad": cap if cap > 0 else None}
    if kg_pend > 0 and sesion:
        ts      = ahora()
        uid     = str(update.effective_user.id)
        usuario = get_usuario(uid)
        guardar_descarga(sesion, kg_pend, usuario, ts, destino_info)
        await update.message.reply_text(armar_confirmacion(sesion, kg_pend, destino_info, 0), parse_mode="Markdown")
    else:
        await update.message.reply_text(f"🚛 Camión *{chasis} / {acoplado}* listo.", parse_mode="Markdown")
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
    supabase.table("silobolsas").insert({"numero": numero, "lote_id": lote_id}).execute()
    await update.message.reply_text(f"🌾 Silobolsa #{numero} abierto. Mandá las descargas.")

# ── /resumen ─────────────────────────────────────────────────
async def cmd_resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid     = str(update.effective_user.id)
    usuario = get_usuario(uid)
    if not usuario:
        await update.message.reply_text("Primero registrate con /start.")
        return
    teclado = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Hoy",          callback_data="res_hoy"),
         InlineKeyboardButton("📆 Esta semana",   callback_data="res_semana"),
         InlineKeyboardButton("🗓 Este mes",      callback_data="res_mes")],
        [InlineKeyboardButton("🚛 Por camión",    callback_data="res_tipo_camion"),
         InlineKeyboardButton("🌾 Por silobolsa", callback_data="res_tipo_silo")],
        [InlineKeyboardButton("👤 Por cliente",   callback_data="res_tipo_cliente"),
         InlineKeyboardButton("🌱 Por lote",      callback_data="res_tipo_lote")],
    ])
    await update.message.reply_text("¿Qué resumen querés ver?", reply_markup=teclado)

async def resumen_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    chat_id = str(update.effective_chat.id)
    uid     = str(update.effective_user.id)
    usuario = get_usuario(uid)
    data    = query.data
    cliente_id = usuario.get("cliente_id") if usuario and usuario["rol"] == "cliente" else None
    if data.startswith("res_tipo_"):
        tipo = data.replace("res_tipo_", "")
        await query.edit_message_text(_resumen_por_tipo(chat_id, tipo, cliente_id), parse_mode="Markdown")
    else:
        periodo = data.replace("res_", "")
        await query.edit_message_text(tool_resumen_periodo(chat_id, periodo, cliente_id), parse_mode="Markdown")

def _resumen_por_tipo(chat_id: str, tipo: str, cliente_id: int = None) -> str:
    desde = ahora().replace(hour=0, minute=0, second=0, microsecond=0)
    if tipo == "camion": return tool_camiones_activos(chat_id)
    elif tipo == "silo":
        r = supabase.table("descargas").select("silobolsa_id, kg, silobolsas(numero)").eq("chat_id", chat_id).eq("destino", "silo").gte("created_at", desde.isoformat()).execute()
        if not r.data: return "No hay descargas a silobolsa hoy."
        silos = {}
        for d in r.data:
            sid = d["silobolsa_id"]; s = d.get("silobolsas") or {}
            if sid not in silos: silos[sid] = {"numero": s.get("numero","?"), "kg": 0}
            silos[sid]["kg"] += float(d["kg"])
        return "🌾 *Silobolsas de hoy*\n\n" + "\n".join(f"Silo #{v['numero']} — *{v['kg']:,.0f} kg*" for v in silos.values())
    elif tipo == "cliente":
        r = supabase.table("descargas").select("cliente_id, kg, clientes(nombre,apellido)").eq("chat_id", chat_id).gte("created_at", desde.isoformat()).execute()
        if not r.data: return "No hay descargas hoy."
        clientes = {}
        for d in r.data:
            c = d.get("clientes"); nombre = f"{c['nombre']} {c['apellido']}" if c else "Sin cliente"
            clientes[nombre] = clientes.get(nombre, 0) + float(d["kg"])
        return "👤 *Por cliente — hoy*\n\n" + "\n".join(f"{n} — *{kg:,.0f} kg*" for n, kg in sorted(clientes.items()))
    elif tipo == "lote":
        r = supabase.table("descargas").select("lote_id, kg, lotes(nombre), campos(nombre)").eq("chat_id", chat_id).gte("created_at", desde.isoformat()).execute()
        if not r.data: return "No hay descargas hoy."
        lotes = {}
        for d in r.data:
            key = f"{(d.get('campos') or {}).get('nombre','?')} / {(d.get('lotes') or {}).get('nombre','?')}"
            lotes[key] = lotes.get(key, 0) + float(d["kg"])
        return "🌱 *Por lote — hoy*\n\n" + "\n".join(f"{k} — *{kg:,.0f} kg*" for k, kg in sorted(lotes.items()))
    return "Tipo no reconocido."

# ── Callbacks destinos ───────────────────────────────────────
async def destino_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    chat_id = str(update.effective_chat.id)
    uid     = str(update.effective_user.id)
    usuario = get_usuario(uid)
    sesion  = get_sesion(chat_id)
    ts      = query.message.date.astimezone(ARG)
    partes  = query.data.split("_")

    # Destino seleccionado pero sin kg aún (viene del menú "Registrar descarga")
    kg_raw = partes[3] if len(partes) > 3 else "0"
    if kg_raw == "?":
        # Guardar destino seleccionado y pedir kg
        if partes[1] == "nuevo":
            context.user_data["conv_state"]        = CAMION_CHASIS if partes[2] == "camion" else None
            context.user_data["kg_pendiente"]      = 0
            context.user_data["destino_pendiente"] = None
            if partes[2] == "silo":
                lote_id = sesion["lote_id"]
                r       = supabase.table("silobolsas").select("numero").eq("lote_id", lote_id).order("numero", desc=True).execute()
                numero  = (r.data[0]["numero"] + 1) if r.data else 1
                nuevo   = supabase.table("silobolsas").insert({"numero": numero, "lote_id": lote_id}).execute()
                context.user_data["destino_pendiente"] = {"tipo": "silo", "id": nuevo.data[0]["id"], "label": f"🌾 Silobolsa #{numero}", "capacidad": None}
                await query.edit_message_text(f"🌾 Silobolsa #{numero} listo.\n\n¿Cuántos kg?")
            else:
                await query.edit_message_text("¿Patente del *chasis* del nuevo camión?", parse_mode="Markdown")
        else:
            tipo    = partes[1]
            dest_id = int(partes[2])
            if tipo == "camion":
                r      = supabase.table("camiones").select("*").eq("id", dest_id).execute()
                camion = r.data[0] if r.data else {}
                context.user_data["destino_pendiente"] = {"tipo": "camion", "id": dest_id, "label": f"🚛 {camion.get('patente_chasis','')} / {camion.get('patente_acoplado','')}", "capacidad": camion.get("capacidad_kg")}
            else:
                r   = supabase.table("silobolsas").select("numero").eq("id", dest_id).execute()
                num = r.data[0]["numero"] if r.data else "?"
                context.user_data["destino_pendiente"] = {"tipo": "silo", "id": dest_id, "label": f"🌾 Silobolsa #{num}", "capacidad": None}
            context.user_data["conv_state"] = DESCARGA_KG
            await query.edit_message_text(f"Destino: *{context.user_data['destino_pendiente']['label']}*\n\n¿Cuántos kg?", parse_mode="Markdown")
        return

    kg = float(kg_raw)

    if partes[1] == "nuevo":
        if partes[2] == "silo":
            lote_id = sesion["lote_id"]
            r       = supabase.table("silobolsas").select("numero").eq("lote_id", lote_id).order("numero", desc=True).execute()
            numero  = (r.data[0]["numero"] + 1) if r.data else 1
            nuevo   = supabase.table("silobolsas").insert({"numero": numero, "lote_id": lote_id}).execute()
            silo_id = nuevo.data[0]["id"]
            if kg > 0:
                destino_info = {"tipo": "silo", "id": silo_id, "label": f"🌾 Silobolsa #{numero}", "capacidad": None}
                guardar_descarga(sesion, kg, usuario, ts, destino_info)
                await query.edit_message_text(armar_confirmacion(sesion, kg, destino_info, 0), parse_mode="Markdown")
            else:
                await query.edit_message_text(f"🌾 Silobolsa #{numero} abierto.")
        else:
            context.user_data["kg_pendiente"] = kg
            context.user_data["conv_state"]   = CAMION_CHASIS
            await query.edit_message_text("¿Patente del *chasis* del nuevo camión?", parse_mode="Markdown")
        return

    tipo    = partes[1]
    dest_id = int(partes[2])
    if tipo == "camion":
        r      = supabase.table("camiones").select("*").eq("id", dest_id).execute()
        camion = r.data[0] if r.data else {}
        acum   = sum(float(d["kg"]) for d in (supabase.table("descargas").select("kg").eq("camion_id", dest_id).eq("chat_id", chat_id).execute().data or []))
        destino_info = {"tipo": "camion", "id": dest_id, "label": f"🚛 {camion.get('patente_chasis','')} / {camion.get('patente_acoplado','')}", "capacidad": camion.get("capacidad_kg")}
        guardar_descarga(sesion, kg, usuario, ts, destino_info)
        await query.edit_message_text(armar_confirmacion(sesion, kg, destino_info, acum), parse_mode="Markdown")
    elif tipo == "silo":
        acum = sum(float(d["kg"]) for d in (supabase.table("descargas").select("kg").eq("silobolsa_id", dest_id).execute().data or []))
        r    = supabase.table("silobolsas").select("numero").eq("id", dest_id).execute()
        num  = r.data[0]["numero"] if r.data else "?"
        destino_info = {"tipo": "silo", "id": dest_id, "label": f"🌾 Silobolsa #{num}", "capacidad": None}
        guardar_descarga(sesion, kg, usuario, ts, destino_info)
        await query.edit_message_text(armar_confirmacion(sesion, kg, destino_info, acum), parse_mode="Markdown")

async def tolva_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("⏳ Los kg sobrantes quedan en la tolva.")

# ── Handler principal ────────────────────────────────────────
INTENCIONES_LOTE   = ["cambiar lote", "nuevo lote", "cambiar de lote", "otro lote", "nuevolote"]
INTENCIONES_CAMION = ["cambiar camion", "nuevo camion", "otro camion", "nuevocamion", "agregar camion"]
INTENCIONES_SILO   = ["nuevo silo", "otro silo", "silobolsa nuevo", "nuevosilo", "abrir silo"]
INTENCIONES_RESUMEN = ["resumen", "totales", "cuanto llevamos", "cuánto llevamos", "ver total"]

def detectar_intencion(texto: str):
    t = texto.lower()
    if any(i in t for i in INTENCIONES_RESUMEN): return "resumen"
    if any(i in t for i in INTENCIONES_LOTE):    return "nuevolote"
    if any(i in t for i in INTENCIONES_CAMION):  return "nuevocamion"
    if any(i in t for i in INTENCIONES_SILO):    return "nuevosilo"
    return None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid     = str(update.effective_user.id)
    usuario = get_usuario(uid)
    msg     = update.message
    texto   = msg.text or ""
    chat_id = str(update.effective_chat.id)
    ts      = msg.date.astimezone(ARG)

    if not usuario:
        await msg.reply_text("Hola! Bienvenido al bot de tolvas.\n\n¿Quién sos?", reply_markup=teclado_roles())
        return

    # Estado de conversación pendiente desde callback
    conv_state = context.user_data.get("conv_state")

    if conv_state == DESCARGA_KG:
        context.user_data["conv_state"] = None
        kg           = parsear_kg(texto)
        sesion       = get_sesion(chat_id)
        destino_info = context.user_data.get("destino_pendiente")
        if not kg:
            await msg.reply_text("No entendí los kg. Escribí solo el número, ej: `13500`", parse_mode="Markdown")
            context.user_data["conv_state"] = DESCARGA_KG
            return
        if not destino_info or not sesion:
            await msg.reply_text("Hubo un error. Intentá de nuevo.")
            return
        acum = sum(float(d["kg"]) for d in (supabase.table("descargas").select("kg")
              .eq("camion_id" if destino_info["tipo"]=="camion" else "silobolsa_id", destino_info["id"])
              .execute().data or []))
        guardar_descarga(sesion, kg, usuario, ts, destino_info)
        await msg.reply_text(armar_confirmacion(sesion, kg, destino_info, acum), parse_mode="Markdown")
        return

    if conv_state == CAMION_CHASIS:
        context.user_data["patente_chasis"] = re.sub(r'\s+', '', texto.upper().strip())
        context.user_data["conv_state"]     = CAMION_ACOPLADO
        await msg.reply_text("¿Patente del *acoplado*?", parse_mode="Markdown")
        return
    if conv_state == CAMION_ACOPLADO:
        context.user_data["patente_acoplado"] = re.sub(r'\s+', '', texto.upper().strip())
        context.user_data["conv_state"]       = CAMION_CAPACIDAD
        await msg.reply_text("¿Capacidad en kg? (ej: `30000`) — Si no sabés escribí *0*", parse_mode="Markdown")
        return
    if conv_state == CAMION_CAPACIDAD:
        context.user_data["conv_state"] = None
        try:
            cap = float(texto.strip().replace('.','').replace(',','.'))
        except ValueError:
            cap = 0
        chasis   = context.user_data["patente_chasis"]
        acoplado = context.user_data["patente_acoplado"]
        kg_pend  = context.user_data.get("kg_pendiente", 0)
        r = supabase.table("camiones").select("*").eq("patente_chasis", chasis).eq("patente_acoplado", acoplado).execute()
        if r.data:
            camion_id = r.data[0]["id"]
            if cap > 0: supabase.table("camiones").update({"capacidad_kg": cap}).eq("id", camion_id).execute()
        else:
            nuevo     = supabase.table("camiones").insert({"patente_chasis": chasis, "patente_acoplado": acoplado, "capacidad_kg": cap if cap > 0 else None}).execute()
            camion_id = nuevo.data[0]["id"]
        sesion       = get_sesion(chat_id)
        destino_info = {"tipo": "camion", "id": camion_id, "label": f"🚛 {chasis} / {acoplado}", "capacidad": cap if cap > 0 else None}
        if kg_pend > 0 and sesion:
            guardar_descarga(sesion, kg_pend, usuario, ts, destino_info)
            await msg.reply_text(armar_confirmacion(sesion, kg_pend, destino_info, 0), parse_mode="Markdown")
        else:
            await msg.reply_text(f"🚛 Camión *{chasis} / {acoplado}* listo.", parse_mode="Markdown")
        return

    if usuario["rol"] == "cliente":
        respuesta = consultar_claude_con_tools(texto, get_sesion(chat_id), usuario, chat_id)
        await msg.reply_text(respuesta, parse_mode="Markdown")
        return

    # Saludos y mensajes generales → mostrar menú
    saludos = ["hola", "buenas", "buen dia", "buenos dias", "buenas tardes", "buenas noches", "hey", "hi"]
    if any(s in texto.lower() for s in saludos):
        sesion = get_sesion(chat_id)
        await mostrar_menu(msg, usuario, sesion, f"Hola {usuario['nombre']}!")
        return

    intencion = detectar_intencion(texto)
    if intencion == "resumen":
        await cmd_resumen(update, context)
        return
    if intencion == "nuevolote":
        await cmd_nuevolote(update, context)
        return
    if intencion == "nuevocamion":
        await cmd_nuevocamion(update, context)
        return
    if intencion == "nuevosilo":
        await cmd_nuevosilo(update, context)
        return

    sesion = get_sesion(chat_id)
    if not sesion or not sesion.get("lote_id"):
        await msg.reply_text("No hay sesión activa.\nUsá /nuevolote para indicar cliente, campo y lote.")
        return

    patentes = parsear_patentes(texto)
    kg       = parsear_kg(texto)

    if kg:
        destinos = get_destinos_abiertos(sesion["lote_id"], chat_id)
        if len(patentes) >= 2:
            chasis, acoplado = patentes[0], patentes[1]
            r = supabase.table("camiones").select("*").eq("patente_chasis", chasis).eq("patente_acoplado", acoplado).execute()
            if r.data:
                camion = r.data[0]; camion_id = camion["id"]
            else:
                nuevo  = supabase.table("camiones").insert({"patente_chasis": chasis, "patente_acoplado": acoplado}).execute()
                camion = nuevo.data[0]; camion_id = camion["id"]
            acum         = sum(float(d["kg"]) for d in (supabase.table("descargas").select("kg").eq("camion_id", camion_id).eq("chat_id", chat_id).execute().data or []))
            destino_info = {"tipo": "camion", "id": camion_id, "label": f"🚛 {chasis} / {acoplado}", "capacidad": camion.get("capacidad_kg")}
            guardar_descarga(sesion, kg, usuario, ts, destino_info)
            await msg.reply_text(armar_confirmacion(sesion, kg, destino_info, acum), parse_mode="Markdown")
            return

        if destinos:
            if len(destinos) == 1:
                d          = destinos[0]
                faltan_str = f" — faltan *{d['faltan']:,.0f} kg*" if d.get("faltan") else ""
                teclado    = InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"✅ Sí, a {d['label']}", callback_data=f"dst_{d['tipo']}_{d['id']}_{kg}")],
                    [InlineKeyboardButton("❌ Otro destino",         callback_data=f"dst_nuevo_camion_{kg}")],
                ])
                await msg.reply_text(f"Son *{kg:,.0f} kg* — ¿van a {d['label']}{faltan_str}?", parse_mode="Markdown", reply_markup=teclado)
            else:
                await msg.reply_text(f"Son *{kg:,.0f} kg* — ¿a dónde van?", parse_mode="Markdown", reply_markup=teclado_destinos(destinos, kg))
        else:
            teclado = InlineKeyboardMarkup([
                [InlineKeyboardButton("🚛 Nuevo camión",    callback_data=f"dst_nuevo_camion_{kg}")],
                [InlineKeyboardButton("🌾 Nuevo silobolsa", callback_data=f"dst_nuevo_silo_{kg}")],
            ])
            await msg.reply_text(f"Son *{kg:,.0f} kg* — ¿a dónde van?", parse_mode="Markdown", reply_markup=teclado)
        return

    respuesta = consultar_claude_con_tools(texto, sesion, usuario, chat_id)
    await msg.reply_text(respuesta, parse_mode="Markdown")

# ── Main ─────────────────────────────────────────────────────
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    registro_conv = ConversationHandler(
        entry_points=[CommandHandler("start", cmd_start), CallbackQueryHandler(elegir_rol, pattern="^rol_")],
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
            LOTE_CLIENTE:         [CallbackQueryHandler(lote_elegir_cliente, pattern="^cli_"),
                                   MessageHandler(filters.TEXT & ~filters.COMMAND, lote_recibir_cliente_texto)],
            LOTE_CAMPO:           [CallbackQueryHandler(lote_elegir_campo,   pattern="^campo_"),
                                   CallbackQueryHandler(lote_elegir_cliente, pattern="^cli_")],
            NUEVO_CLIENTE_NOMBRE: [MessageHandler(filters.TEXT & ~filters.COMMAND, nuevo_cliente_nombre)],
            NUEVO_CAMPO_NOMBRE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, nuevo_campo_nombre)],
            LOTE_LOTE:            [CallbackQueryHandler(lote_elegir_lote,    pattern="^lote_")],
            NUEVO_LOTE_NOMBRE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, nuevo_lote_nombre)],
        },
        fallbacks=[]
    )

    camion_conv = ConversationHandler(
        entry_points=[CommandHandler("nuevocamion", cmd_nuevocamion)],
        states={
            NUEVO_CAMION_CHASIS:    [MessageHandler(filters.TEXT & ~filters.COMMAND, nuevo_camion_chasis)],
            NUEVO_CAMION_ACOPLADO:  [MessageHandler(filters.TEXT & ~filters.COMMAND, nuevo_camion_acoplado)],
            NUEVO_CAMION_CAPACIDAD: [MessageHandler(filters.TEXT & ~filters.COMMAND, nuevo_camion_capacidad)],
        },
        fallbacks=[]
    )

    app.add_handler(registro_conv)
    app.add_handler(lote_conv)
    app.add_handler(camion_conv)
    app.add_handler(CallbackQueryHandler(menu_callback,    pattern="^menu_"))
    app.add_handler(CallbackQueryHandler(resumen_callback, pattern="^res_"))
    app.add_handler(CallbackQueryHandler(tolva_callback,   pattern="^dst_tolva$"))
    app.add_handler(CallbackQueryHandler(destino_callback, pattern="^dst_"))
    app.add_handler(CommandHandler("ayuda",       cmd_ayuda))
    app.add_handler(CommandHandler("resumen",     cmd_resumen))
    app.add_handler(CommandHandler("nuevosilo",   cmd_nuevosilo))
    app.add_handler(CommandHandler("nuevocamion", cmd_nuevocamion))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot corriendo...")
    app.run_polling()
