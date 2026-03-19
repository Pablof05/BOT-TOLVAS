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
    r = supabase.table("clientes").select("*").eq("contratista_id", contratista_id).order("apellido").execute()
    return r.data or []

def get_campos(cliente_id: int):
    r = supabase.table("campos").select("*").eq("cliente_id", cliente_id).order("nombre").execute()
    return r.data or []

def get_lotes(campo_id: int):
    r = supabase.table("lotes").select("*").eq("campo_id", campo_id).order("nombre").execute()
    return r.data or []

def get_operarios(contratista_id: int):
    r = supabase.table("usuarios").select("id, nombre").eq("contratista_id", contratista_id).eq("rol", "operario").order("nombre").execute()
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

def get_descargas_lote(lote_id: int, desde=None, operario_id=None):
    q = supabase.table("descargas").select(
        "kg, destino, camion_id, silobolsa_id, operario_id, created_at, "
        "camiones(patente_chasis, patente_acoplado, capacidad_kg, cerrado), "
        "silobolsas(numero, cerrado), "
        "usuarios(nombre)"
    ).eq("lote_id", lote_id)
    if desde:
        q = q.gte("created_at", desde)
    if operario_id:
        q = q.eq("operario_id", operario_id)
    return q.execute().data or []

def construir_resumen(cliente_id: int, periodo: str, campo_id_filtro=None,
                      lote_id_filtro=None, operario_id=None, tipo=None):
    desde    = desde_periodo(periodo)
    campos   = get_campos(cliente_id)
    resultado = []
    total_kg_global = 0.0

    for campo in campos:
        if campo_id_filtro and campo["id"] != campo_id_filtro:
            continue
        lotes      = get_lotes(campo["id"])
        lotes_data = []

        for lote in lotes:
            if lote_id_filtro and lote["id"] != lote_id_filtro:
                continue
            descargas = get_descargas_lote(lote["id"], desde, operario_id)
            if not descargas:
                continue

            camiones = {}
            silos    = {}
            total_lote = 0.0

            for d in descargas:
                kg = float(d["kg"])
                if d["destino"] == "camion" and d.get("camion_id"):
                    if tipo == "silo":
                        continue
                    cid = d["camion_id"]
                    c   = d.get("camiones") or {}
                    if cid not in camiones:
                        camiones[cid] = {
                            "chasis":    c.get("patente_chasis", "?"),
                            "acoplado":  c.get("patente_acoplado", "?"),
                            "capacidad": c.get("capacidad_kg"),
                            "cerrado":   c.get("cerrado", False),
                            "kg": 0.0,
                        }
                    camiones[cid]["kg"] += kg
                    total_lote += kg
                elif d["destino"] == "silo" and d.get("silobolsa_id"):
                    if tipo == "camion":
                        continue
                    sid = d["silobolsa_id"]
                    s   = d.get("silobolsas") or {}
                    if sid not in silos:
                        silos[sid] = {
                            "numero":  s.get("numero", "?"),
                            "cerrado": s.get("cerrado", False),
                            "kg": 0.0,
                        }
                    silos[sid]["kg"] += kg
                    total_lote += kg

            if not camiones and not silos:
                continue

            total_kg_global += total_lote
            lotes_data.append({
                "nombre":   lote["nombre"],
                "grano":    lote.get("grano", ""),
                "total_kg": total_lote,
                "camiones": sorted(camiones.values(), key=lambda x: x["chasis"]),
                "silos":    sorted(silos.values(),    key=lambda x: x["numero"]),
            })

        if lotes_data:
            resultado.append({
                "id":     campo["id"],
                "nombre": campo["nombre"],
                "lotes":  lotes_data,
            })

    return resultado, total_kg_global


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

    rol         = session["rol"]
    nombre      = session["nombre"]
    periodo     = request.args.get("periodo", "todo")
    campo_id    = int(request.args.get("campo_id",    0)) or None
    lote_id     = int(request.args.get("lote_id",     0)) or None
    operario_id = int(request.args.get("operario_id", 0)) or None
    tipo        = request.args.get("tipo", "") or None   # "camion" | "silo" | None

    operarios = []

    if rol in ("contratista", "operario"):
        cont_id  = session["cont_id"]
        clientes = get_clientes(cont_id)
        cli_id   = int(request.args.get("cli_id", 0)) or (clientes[0]["id"] if clientes else None)
        cliente_actual = next((c for c in clientes if c["id"] == cli_id),
                              clientes[0] if clientes else None)
        campos    = get_campos(cli_id) if cli_id else []
        lotes     = get_lotes(campo_id) if campo_id else []
        operarios = get_operarios(cont_id)
        resumen, total_kg = (
            construir_resumen(cli_id, periodo, campo_id, lote_id, operario_id, tipo)
            if cli_id else ([], 0.0)
        )
    else:
        cli_id         = session["cli_id"]
        clientes       = []
        cliente_actual = None
        campos         = get_campos(cli_id)
        lotes          = get_lotes(campo_id) if campo_id else []
        resumen, total_kg = construir_resumen(
            cli_id, periodo, campo_id, lote_id, operario_id, tipo
        )

    total_camiones = sum(len(l["camiones"]) for c in resumen for l in c["lotes"])
    total_silos    = sum(len(l["silos"])    for c in resumen for l in c["lotes"])

    return render_template("dashboard.html",
        rol=rol, nombre=nombre, periodo=periodo,
        clientes=clientes, cli_id=cli_id, cliente_actual=cliente_actual,
        campos=campos, campo_id=campo_id,
        lotes=lotes, lote_id=lote_id,
        operarios=operarios, operario_id=operario_id,
        tipo=tipo or "",
        resumen=resumen,
        total_kg=total_kg,
        total_camiones=total_camiones,
        total_silos=total_silos,
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
