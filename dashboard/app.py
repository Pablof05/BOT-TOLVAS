import os
from datetime import datetime, timezone, timedelta
from flask import Flask, render_template, request, session, redirect, url_for
from supabase import create_client

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "tolvas-secret-2024")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
supabase     = create_client(SUPABASE_URL, SUPABASE_KEY)
ARG          = timezone(timedelta(hours=-3))

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

def get_clientes(contratista_id: int):
    r = supabase.table("clientes").select("*").eq("contratista_id", contratista_id).execute()
    return r.data or []

def get_campos(cliente_id: int):
    r = supabase.table("campos").select("*").eq("cliente_id", cliente_id).order("nombre").execute()
    return r.data or []

def get_lotes(campo_id: int):
    r = supabase.table("lotes").select("*").eq("campo_id", campo_id).order("nombre").execute()
    return r.data or []

def desde_periodo(periodo: str):
    ahora_ts = datetime.now(ARG)
    if periodo == "hoy":
        return ahora_ts.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    elif periodo == "semana":
        return (ahora_ts - timedelta(days=7)).isoformat()
    elif periodo == "mes":
        return ahora_ts.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    return None

def get_descargas_lote(lote_id: int, desde=None):
    q = supabase.table("descargas").select(
        "kg, destino, camion_id, silobolsa_id, created_at, "
        "camiones(patente_chasis, patente_acoplado, capacidad_kg, cerrado), "
        "silobolsas(numero, cerrado)"
    ).eq("lote_id", lote_id)
    if desde:
        q = q.gte("created_at", desde)
    return q.execute().data or []

def construir_resumen(cliente_id: int, periodo: str, campo_id_filtro=None, lote_id_filtro=None):
    desde = desde_periodo(periodo)
    campos = get_campos(cliente_id)
    resultado = []

    for campo in campos:
        if campo_id_filtro and campo["id"] != campo_id_filtro:
            continue
        lotes = get_lotes(campo["id"])
        lotes_data = []
        for lote in lotes:
            if lote_id_filtro and lote["id"] != lote_id_filtro:
                continue
            descargas = get_descargas_lote(lote["id"], desde)
            if not descargas:
                continue
            camiones = {}
            silos    = {}
            for d in descargas:
                if d["destino"] == "camion" and d.get("camion_id"):
                    cid = d["camion_id"]
                    c   = d.get("camiones") or {}
                    if cid not in camiones:
                        camiones[cid] = {
                            "chasis":    c.get("patente_chasis", "?"),
                            "acoplado":  c.get("patente_acoplado", "?"),
                            "capacidad": c.get("capacidad_kg"),
                            "cerrado":   c.get("cerrado", False),
                            "kg": 0
                        }
                    camiones[cid]["kg"] += float(d["kg"])
                elif d["destino"] == "silo" and d.get("silobolsa_id"):
                    sid = d["silobolsa_id"]
                    s   = d.get("silobolsas") or {}
                    if sid not in silos:
                        silos[sid] = {
                            "numero":  s.get("numero", "?"),
                            "cerrado": s.get("cerrado", False),
                            "kg": 0
                        }
                    silos[sid]["kg"] += float(d["kg"])

            total_lote = sum(float(d["kg"]) for d in descargas)
            lotes_data.append({
                "nombre":   lote["nombre"],
                "grano":    lote.get("grano", ""),
                "total_kg": total_lote,
                "camiones": list(camiones.values()),
                "silos":    list(silos.values()),
            })

        if lotes_data:
            resultado.append({
                "id":     campo["id"],
                "nombre": campo["nombre"],
                "lotes":  lotes_data,
            })

    return resultado

# ── Rutas ────────────────────────────────────────────────────
@app.route("/", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        telegram_id = request.form.get("telegram_id", "").strip()

        cont = get_contratista(telegram_id)
        if cont:
            session["telegram_id"] = telegram_id
            session["rol"]         = "contratista"
            session["nombre"]      = f"{cont['nombre']} {cont['apellido']}"
            session["cont_id"]     = cont["id"]
            return redirect(url_for("dashboard"))

        usr = get_usuario(telegram_id)
        if usr:
            session["telegram_id"] = telegram_id
            session["rol"]         = "operario"
            session["nombre"]      = usr["nombre"]
            session["cont_id"]     = usr["contratista_id"]
            return redirect(url_for("dashboard"))

        cli = get_cliente_by_telegram(telegram_id)
        if cli:
            session["telegram_id"] = telegram_id
            session["rol"]         = "cliente"
            session["nombre"]      = f"{cli['nombre']} {cli['apellido']}"
            session["cli_id"]      = cli["id"]
            return redirect(url_for("dashboard"))

        error = "No se encontró ninguna cuenta con ese Telegram ID. Usá el bot primero."

    return render_template("login.html", error=error)

@app.route("/dashboard")
def dashboard():
    if "telegram_id" not in session:
        return redirect(url_for("login"))

    rol      = session["rol"]
    nombre   = session["nombre"]
    periodo  = request.args.get("periodo", "todo")
    campo_id = int(request.args.get("campo_id", 0)) or None
    lote_id  = int(request.args.get("lote_id", 0)) or None

    if rol in ("contratista", "operario"):
        cont_id  = session["cont_id"]
        clientes = get_clientes(cont_id)
        cli_id   = int(request.args.get("cli_id", 0)) or (clientes[0]["id"] if clientes else None)
        cliente_actual = next((c for c in clientes if c["id"] == cli_id), clientes[0] if clientes else None)
        resumen  = construir_resumen(cli_id, periodo, campo_id, lote_id) if cli_id else []
        campos   = get_campos(cli_id) if cli_id else []
        lotes    = get_lotes(campo_id) if campo_id else []
    else:
        cli_id         = session["cli_id"]
        clientes       = []
        cliente_actual = None
        resumen        = construir_resumen(cli_id, periodo, campo_id, lote_id)
        campos         = get_campos(cli_id)
        lotes          = get_lotes(campo_id) if campo_id else []

    return render_template("dashboard.html",
        rol=rol, nombre=nombre, periodo=periodo,
        clientes=clientes, cli_id=cli_id, cliente_actual=cliente_actual,
        campos=campos, campo_id=campo_id,
        lotes=lotes, lote_id=lote_id,
        resumen=resumen,
    )

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
