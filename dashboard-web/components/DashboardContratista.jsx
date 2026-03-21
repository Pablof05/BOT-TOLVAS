function StatCard({ label, value, icon, sub }) {
  return (
    <div className="bg-white rounded-2xl shadow p-5">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm text-gray-500 font-medium">{label}</span>
        <span className="text-2xl">{icon}</span>
      </div>
      <p className="text-3xl font-bold text-gray-800">{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-1">{sub}</p>}
    </div>
  )
}

function BarraCamion({ camion }) {
  const { patente_chasis, patente_acoplado, capacidad_kg, acumulado } = camion
  const pct = capacidad_kg ? Math.min((acumulado / capacidad_kg) * 100, 100) : null
  const faltan = capacidad_kg ? Math.max(capacidad_kg - acumulado, 0) : null

  const color = pct == null ? 'bg-blue-400'
    : pct >= 95 ? 'bg-red-500'
    : pct >= 75 ? 'bg-amber-400'
    : 'bg-green-500'

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between text-sm">
        <span className="font-mono font-semibold text-gray-800">
          {patente_chasis}{patente_acoplado ? ` / ${patente_acoplado}` : ''}
        </span>
        <span className="text-gray-500 text-xs">
          {acumulado.toLocaleString('es-AR')} kg
          {capacidad_kg ? ` / ${capacidad_kg.toLocaleString('es-AR')} kg` : ''}
        </span>
      </div>
      {pct != null ? (
        <>
          <div className="w-full h-2.5 bg-gray-100 rounded-full overflow-hidden">
            <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${pct}%` }} />
          </div>
          <div className="flex justify-between text-xs text-gray-400">
            <span>{pct.toFixed(0)}% cargado</span>
            <span>faltan {faltan.toLocaleString('es-AR')} kg</span>
          </div>
        </>
      ) : (
        <div className="w-full h-2.5 bg-gray-100 rounded-full overflow-hidden">
          <div className="h-full rounded-full bg-blue-400" style={{ width: '100%', opacity: 0.3 }} />
        </div>
      )}
    </div>
  )
}

export default function DashboardContratista({
  camionesAbiertos, camionesCerrados, operarios, clientes, descargas, camionesActivosData = []
}) {
  const totalKg = descargas.reduce((acc, d) => acc + (d.kg || 0), 0)
  const toneladas = (totalKg / 1000).toLocaleString('es-AR', { maximumFractionDigits: 1 })

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-800 mb-6">Resumen general</h1>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <StatCard
          label="Toneladas descargadas"
          value={`${toneladas} t`}
          icon="⚖️"
          sub={`${descargas.length} viajes registrados`}
        />
        <StatCard
          label="Camiones activos"
          value={camionesAbiertos}
          icon="🚛"
          sub={`${camionesCerrados} cerrados`}
        />
        <StatCard label="Clientes"   value={clientes}   icon="🧑‍🌾" />
        <StatCard label="Operarios"  value={operarios}  icon="👷" />
      </div>

      {camionesActivosData.length > 0 && (
        <div className="mt-8">
          <h2 className="text-lg font-semibold text-gray-700 mb-4">Carga de camiones activos</h2>
          <div className="bg-white rounded-2xl shadow p-5 grid grid-cols-1 md:grid-cols-2 gap-6">
            {camionesActivosData.map(c => (
              <BarraCamion key={c.id} camion={c} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
