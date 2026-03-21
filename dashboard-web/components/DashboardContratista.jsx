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

export default function DashboardContratista({
  camionesAbiertos, camionesCerrados, operarios, clientes, descargas
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
    </div>
  )
}
