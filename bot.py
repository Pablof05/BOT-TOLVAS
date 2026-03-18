import os, re, json, logging
from datetime import datetime, timezone, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
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

# ── Helpers BD ───────────────────────────────────────────────
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

def get_historial(chat_id: str, limite: int = 10):
    r = (supabase.table("descargas")
         .select("kg, destino, created_at, "
                 "camiones(patente_chasis,patente_acoplado), "
                 "silobolsas(numero), clientes(nombre,apellido), "
                 "lotes(nombre), campos(nombre)")
         .eq("chat_id", chat_id)
         .order("created_at", desc=True)
         .limit(limite)
         .execute())
    return r.data or []

def get_historial_mensajes(chat_id: str):
    r = (supabase.table("historial_chat")
         .select("rol, mensaje")
         .eq("chat_id", chat_id)
         .order("created_at", desc=True)
         .limit(12)
         .execute())
    msgs = list(reversed(r.data or []))
    return [{"role": m["rol"], "content": m["mensaje"]} for m in msgs]

def guardar_mensaje(chat_id: str, rol: str, mensaje: str):
    supabase.table("historial_chat").insert({
        "chat_id":    chat_id,
        "rol":        rol,
        "mensaje":    mensaje,
        "created_at": ahora().isoformat()
    }).execute()

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

# ── Contexto para Claude ─────────────────────────────────────
def construir_contexto(usuario, sesion, historial_descargas):
    ctx = {"usuario": usuario, "sesion_activa": None, "ultimas_descargas": []}

    if sesion:
        cliente = sesion.get("clientes") or {}
        ctx["sesion_activa"] = {
            "cliente":  f"{cliente.get('nombre','')} {cliente.get('apellido','')}".strip(),
            "campo":    (sesion.get("campos")    or {}).get("nombre"),
            "lote":     (sesion.get("lotes")     or {}).get("nombre"),
            "destino":  sesion.get("destino"),
            "camion":   sesion.get("camiones"),
            "silobolsa": sesion.get("silobolsas"),
        }

    for d in historial_descargas:
        cliente = d.get("clientes") or {}
        ctx["ultimas_descargas"].append({
            "kg":       d["kg"],
            "destino":  d["destino"],
            "camion":   d.get("camiones"),
            "silo":     d.get("silobolsas"),
            "cliente":  f"{cliente.get('nombre','')} {cliente.get('apellido','')}".strip(),
            "lote":     (d.get("lotes")   or {}).get("nombre"),
            "campo":    (d.get("campos")  or {}).get("nombre"),
            "hora":     d["created_at"],
        })

    return json.dumps(ctx, ensure_ascii=False, default=str)

SYSTEM_PROMPT = """Sos el asistente del sistema de tolvas de una empresa agropecuaria argentina.
Tu trabajo es interpretar los mensajes de operarios, clientes y encargados, y responder SIEMPRE con un JSON.

ROLES:
- operario: puede registrar descargas y consultar estado
- cliente: solo puede consultar sus propios datos
- encargado: puede ver todo y gestionar sesiones

ACCIONES DISPONIBLES (respondé siempre con una de estas):

1. REGISTRAR DESCARGA — cuando el operario informa kg y destino:
{"accion": "registrar", "kg": 5400, "patente_chasis": "AB123CD", "patente_acoplado": "XY456ZW", "capacidad_kg": 30000}
Si va a silobolsa omitir patentes. capacidad_kg es opcional.

2. NUEVA SESION — cuando cambia cliente/campo/lote:
{"accion": "nueva_sesion", "cliente_nombre": "García", "cliente_apellido": "Juan", "campo": "La Colorada", "lote": "Lote 3"}

3. NUEVO DESTINO CAMION:
{"accion": "nuevo_camion", "patente_chasis": "AB123CD", "patente_acoplado": "XY456ZW", "capacidad_kg": 30000}

4. NUEVO SILO:
{"accion": "nuevo_silo"}

5. RESUMEN — cuando piden datos/totales:
{"accion": "resumen", "periodo": "hoy"} — periodo puede ser: hoy, semana, mes

6. ESTADO CAMION:
{"accion": "estado_camion", "patente": "AB123CD"}

7. REGISTRAR USUARIO — cuando alguien nuevo se presenta:
{"accion": "registrar_usuario", "nombre": "Juan Pérez", "rol": "operario"}
rol puede ser: operario, cliente, encargado

8. PREGUNTAR — cuando falta información para completar una acción:
{"accion": "preguntar", "mensaje": "¿Cuántos kg descargaste?"}

9. RESPONDER — para respuestas informativas o que no requieren acción en BD:
{"accion": "responder", "mensaje": "Hola! Para registrar una descarga..."}

REGLAS IMPORTANTES:
- Los operarios hablan informal y a veces con errores, interpretá con criterio
- Si dicen "32 tones" o "32 t" interpretá como 32000 kg
- Las patentes argentinas son formato AAA999 (vieja) o AA999AA (nueva)
- Si falta info crítica para registrar, preguntá UNA SOLA cosa por vez
- Si ya hay sesión activa con cliente/campo/lote, NO la pierdas salvo que explícitamente cambien
- Respondé siempre en español rioplatense, informal y directo
- NUNCA respondas con texto libre, SIEMPRE con JSON válido
"""

# ── Ejecutar acción devuelta por Claude ──────────────────────
async def ejecutar_accion(accion_json: dict, usuario, sesion, chat_id: str, ts) -> str:
    accion = accion_json.get("accion")

    if accion == "preguntar" or accion == "responder":
        return accion_json.get("mensaje", "")

    if accion == "registrar_usuario":
        nombre = accion_json.get("nombre", "")
        rol    = accion_json.get("rol", "operario")
        if rol not in ("operario", "cliente", "encargado"):
            rol = "operario"
        supabase.table("usuarios").insert({
            "telegram_id": str(usuario["telegram_id"] if usuario else ""),
            "nombre":      nombre,
            "rol":         rol,
            "activo":      True
        }).execute()
        msgs = {
            "operario":  "Ya podés registrar descargas. Cuando quieras cargar una descarga simplemente mandame los kg y la patente.",
            "cliente":   "Podés pedirme el resumen de tus granos cuando quieras.",
            "encargado": "Tenés acceso completo al sistema."
        }
        return f"✅ Bienvenido *{nombre}*! Quedaste registrado como *{rol}*.\n\n{msgs[rol]}"

    if accion == "nueva_sesion":
        nombre_c   = accion_json.get("cliente_nombre", "")
        apellido_c = accion_json.get("cliente_apellido", "")
        campo_n    = accion_json.get("campo", "")
        lote_n     = accion_json.get("lote", "")

        # Cliente
        r = supabase.table("clientes").select("*").ilike("apellido", f"%{apellido_c}%").execute()
        if not r.data:
            r = supabase.table("clientes").select("*").ilike("nombre", f"%{nombre_c}%").execute()
        if r.data:
            cliente_id = r.data[0]["id"]
            cliente_str = f"{r.data[0]['nombre']} {r.data[0]['apellido']}"
        else:
            nuevo = supabase.table("clientes").insert({"nombre": nombre_c, "apellido": apellido_c}).execute()
            cliente_id  = nuevo.data[0]["id"]
            cliente_str = f"{nombre_c} {apellido_c}"

        # Campo
        r = supabase.table("campos").select("*").eq("cliente_id", cliente_id).ilike("nombre", f"%{campo_n}%").execute()
        if r.data:
            campo_id = r.data[0]["id"]
        else:
            nuevo    = supabase.table("campos").insert({"nombre": campo_n, "cliente_id": cliente_id}).execute()
            campo_id = nuevo.data[0]["id"]

        # Lote
        r = supabase.table("lotes").select("*").eq("campo_id", campo_id).ilike("nombre", f"%{lote_n}%").execute()
        if r.data:
            lote_id = r.data[0]["id"]
        else:
            nuevo   = supabase.table("lotes").insert({"nombre": lote_n, "campo_id": campo_id}).execute()
            lote_id = nuevo.data[0]["id"]

        supabase.table("sesion_activa").upsert({
            "chat_id":     chat_id,
            "cliente_id":  cliente_id,
            "campo_id":    campo_id,
            "lote_id":     lote_id,
            "destino":     None,
            "camion_id":   None,
            "silo_id":     None,
            "iniciada_at": ahora().isoformat()
        }).execute()
        return f"✅ Sesión iniciada\n👤 *{cliente_str}* / {campo_n} / {lote_n}\n\n¿Las descargas van a camión o silobolsa?"

    if accion == "nuevo_camion":
        chasis   = accion_json.get("patente_chasis", "").upper()
        acoplado = accion_json.get("patente_acoplado", "").upper()
        cap      = accion_json.get("capacidad_kg")
        r = supabase.table("camiones").select("*").eq("patente_chasis", chasis).eq("patente_acoplado", acoplado).execute()
        if r.data:
            camion_id = r.data[0]["id"]
            if cap:
                supabase.table("camiones").update({"capacidad_kg": cap}).eq("id", camion_id).execute()
        else:
            nuevo     = supabase.table("camiones").insert({
                "patente_chasis": chasis, "patente_acoplado": acoplado,
                "capacidad_kg": cap
            }).execute()
            camion_id = nuevo.data[0]["id"]
        supabase.table("sesion_activa").update({
            "destino": "camion", "camion_id": camion_id, "silo_id": None
        }).eq("chat_id", chat_id).execute()
        cap_str = f" ({cap:,.0f} kg)" if cap else ""
        return f"🚛 Camión *{chasis} / {acoplado}*{cap_str} listo. Mandá las descargas."

    if accion == "nuevo_silo":
        if not sesion or not sesion.get("lote_id"):
            return "Primero indicame el cliente, campo y lote."
        lote_id = sesion["lote_id"]
        r       = supabase.table("silobolsas").select("numero").eq("lote_id", lote_id).order("numero", desc=True).execute()
        numero  = (r.data[0]["numero"] + 1) if r.data else 1
        nuevo   = supabase.table("silobolsas").insert({"numero": numero, "lote_id": lote_id}).execute()
        supabase.table("sesion_activa").update({
            "destino": "silo", "silo_id": nuevo.data[0]["id"], "camion_id": None
        }).eq("chat_id", chat_id).execute()
        return f"🌾 Silobolsa #{numero} abierto. Mandá las descargas."

    if accion == "registrar":
        if not sesion or not sesion.get("lote_id"):
            return "Antes de registrar necesito saber el cliente, campo y lote. ¿Me los decís?"

        kg       = float(accion_json.get("kg", 0))
        chasis   = (accion_json.get("patente_chasis") or "").upper()
        acoplado = (accion_json.get("patente_acoplado") or "").upper()
        cap      = accion_json.get("capacidad_kg")

        destino = sesion.get("destino")

        if chasis and acoplado:
            r = supabase.table("camiones").select("*").eq("patente_chasis", chasis).eq("patente_acoplado", acoplado).execute()
            if r.data:
                camion    = r.data[0]
                camion_id = camion["id"]
                if cap:
                    supabase.table("camiones").update({"capacidad_kg": cap}).eq("id", camion_id).execute()
                    camion["capacidad_kg"] = cap
            else:
                nuevo     = supabase.table("camiones").insert({
                    "patente_chasis": chasis, "patente_acoplado": acoplado,
                    "capacidad_kg": cap
                }).execute()
                camion    = nuevo.data[0]
                camion_id = camion["id"]
            supabase.table("sesion_activa").update({
                "destino": "camion", "camion_id": camion_id, "silo_id": None
            }).eq("chat_id", chat_id).execute()
            destino           = "camion"
            sesion["destino"] = "camion"
            sesion["camion_id"] = camion_id
            sesion["camiones"]  = camion

        elif not destino:
            return "¿Esta descarga va a camión o silobolsa?"

        data = {
            "kg":           kg,
            "destino":      destino,
            "camion_id":    sesion.get("camion_id") if destino == "camion" else None,
            "silobolsa_id": sesion.get("silo_id")   if destino == "silo"   else None,
            "lote_id":      sesion.get("lote_id"),
            "campo_id":     sesion.get("campo_id"),
            "cliente_id":   sesion.get("cliente_id"),
            "tolva":        chat_id,
            "operario_id":  usuario["id"] if usuario else None,
            "chat_id":      chat_id,
            "created_at":   ts.isoformat(),
        }
        supabase.table("descargas").insert(data).execute()

        cliente_obj  = sesion.get("clientes") or {}
        cliente_str  = f"{cliente_obj.get('nombre','')} {cliente_obj.get('apellido','')}".strip() or "—"
        campo_str    = (sesion.get("campos")  or {}).get("nombre", "—")
        lote_str     = (sesion.get("lotes")   or {}).get("nombre", "—")

        if destino == "camion":
            camion_obj   = sesion.get("camiones") or {}
            acumulado    = kg_acumulado_camion(sesion["camion_id"], chat_id) + kg
            capacidad    = camion_obj.get("capacidad_kg") or cap
            chasis_str   = camion_obj.get("patente_chasis",   chasis   or "—")
            acoplado_str = camion_obj.get("patente_acoplado", acoplado or "—")
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
        return "\n".join(lineas)

    if accion == "resumen":
        periodo  = accion_json.get("periodo", "hoy")
        ahora_ts = ahora()
        if periodo == "mes":
            desde  = ahora_ts.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            titulo = f"Mes {ahora_ts.strftime('%B %Y')}"
        elif periodo == "semana":
            desde  = ahora_ts - timedelta(days=7)
            titulo = "Últimos 7 días"
        else:
            desde  = ahora_ts.replace(hour=0, minute=0, second=0, microsecond=0)
            titulo = f"Hoy {ahora_ts.strftime('%d/%m/%Y')}"

        q = (supabase.table("descargas")
             .select("kg, destino, camion_id, silobolsa_id, cliente_id, clientes(nombre,apellido)")
             .gte("created_at", desde.isoformat()))
        if usuario and usuario["rol"] == "cliente":
            q = q.eq("cliente_id", usuario.get("cliente_id"))
        res = q.order("created_at", desc=True).execute()

        if not res.data:
            return f"Sin registros para {titulo}."

        total_kg     = sum(float(r["kg"]) for r in res.data)
        camiones_set = {r["camion_id"]    for r in res.data if r["camion_id"]}
        silos_set    = {r["silobolsa_id"] for r in res.data if r["silobolsa_id"]}

        lineas = [
            f"📊 *{titulo}*\n",
            f"Total: *{total_kg:,.0f} kg*",
            f"Camiones: {len(camiones_set)}  |  Silobolsas: {len(silos_set)}",
            f"Descargas: {len(res.data)}\n"
        ]
        if usuario and usuario["rol"] == "encargado":
            clientes = {}
            for r in res.data:
                c      = r.get("clientes")
                nombre = f"{c['nombre']} {c['apellido']}" if c else "Sin cliente"
                clientes[nombre] = clientes.get(nombre, 0) + float(r["kg"])
            for nombre, kg in sorted(clientes.items()):
                lineas.append(f"👤 *{nombre}*: {kg:,.0f} kg")
        return "\n".join(lineas)

    if accion == "estado_camion":
        patente = accion_json.get("patente", "").upper()
        r = supabase.table("camiones").select("*").eq("patente_chasis", patente).execute()
        if not r.data:
            r = supabase.table("camiones").select("*").eq("patente_acoplado", patente).execute()
        if not r.data:
            return f"No encontré el camión {patente}."
        camion    = r.data[0]
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
        return "\n".join(lineas)

    return "No entendí eso. ¿Podés repetirlo?"

# ── Llamada a Claude ─────────────────────────────────────────
def consultar_claude(historial_msgs: list, contexto: str, mensaje_usuario: str) -> dict:
    mensajes = historial_msgs + [{"role": "user", "content": mensaje_usuario}]
    try:
        resp = claude.messages.create(
            model="claude-haiku-4-5",
            max_tokens=512,
            system=SYSTEM_PROMPT + f"\n\nCONTEXTO ACTUAL:\n{contexto}",
            messages=mensajes
        )
        texto = resp.content[0].text.strip()
        texto = re.sub(r'^```json\s*|\s*```$', '', texto, flags=re.MULTILINE).strip()
        # Extraer solo el primer JSON válido
        match = re.search(r'\{.*?\}', texto, re.DOTALL)
        if match:
            return json.loads(match.group())
        return json.loads(texto)
    except Exception as e:
        logging.error(f"Error Claude: {e}")
        return {"accion": "responder", "mensaje": "Hubo un error, intentá de nuevo."}
# ── Handler principal ────────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg     = update.message
    texto   = msg.text or ""
    uid     = str(update.effective_user.id)
    chat_id = str(update.effective_chat.id)
    ts      = msg.date.astimezone(ARG)

    usuario           = get_usuario(uid)
    sesion            = get_sesion(chat_id)
    historial_descargas = get_historial(chat_id)
    historial_msgs    = get_historial_mensajes(chat_id)
    contexto          = construir_contexto(usuario, sesion, historial_descargas)

    # Guardar mensaje del usuario
    guardar_mensaje(chat_id, "user", texto)

    # Consultar Claude
    accion_json = consultar_claude(historial_msgs, contexto, texto)
    respuesta   = await ejecutar_accion(accion_json, usuario, sesion, chat_id, ts)

    # Guardar respuesta del bot
    guardar_mensaje(chat_id, "assistant", respuesta)

    await msg.reply_text(respuesta, parse_mode="Markdown")

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_message(update, context)

async def cmd_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update.message.text = "/ayuda"
    await handle_message(update, context)

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("ayuda",  cmd_ayuda))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Bot corriendo...")
    app.run_polling()
