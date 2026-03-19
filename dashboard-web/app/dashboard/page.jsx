import { createClient } from '../../lib/supabase-server'

async function getContratistaId(supabase) {
  const { data: { user } } = await supabase.auth.getUser()
  const { data } = await supabase
    .from('contratistas')
    .select('id')
    .eq('user_id', user.id)
    .single()
  return data?.id
}

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

export default async function DashboardPage() {
  const supabase = createClient()
  const contratistaId = await getContratistaId(supabase)

  if (!contratistaId) {
    return (
      <div className="text-center py-20 text-gray-500">
        <p className="text-lg">No hay contratista vinculado a tu cuenta.</p>
        <p className="text-sm mt-2">Pedile al administrador que vincule tu usuario.</p>
      </div>
    )
  }

  // KPIs en paralelo
  const [
    { data: camionesAbiertos },
    { data: camionesCerrados },
    { data: silobolsas },
    { data: descargas },
    { data: operarios },
    { data: clientes },
  ] = await Promise.all([
    supabase.from('camiones').select('id, capacidad_kg').eq('contratista_id', contratistaId).eq('cerrado', false),
    supabase.from('camiones').select('id').eq('contratista_id', contratistaId).eq('cerrado', true),
    supabase.from('silobolsas')
      .select('id, cerrado, lotes!inner(campo_id, campos!inner(cliente_id, contratistas:clientes!inner(contratista_id)))')
      .eq('lotes.campos.clientes.contratista_id', contratistaId),
    supabase.from('descargas').select('kg, camiones!inner(contratista_id)').eq('camiones.contratista_id', contratistaId),
    supabase.from('usuarios').select('id').eq('contratista_id', contratistaId).eq('rol', 'operario'),
    supabase.from('clientes').select('id').eq('contratista_id', contratistaId),
  ])

  const totalKg = descargas?.reduce((acc, d) => acc + (d.kg || 0), 0) ?? 0
  const toneladas = (totalKg / 1000).toLocaleString('es-AR', { maximumFractionDigits: 1 })

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-800 mb-6">Resumen general</h1>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-8">
        <StatCard
          label="Toneladas descargadas"
          value={`${toneladas} t`}
          icon="⚖️"
          sub={`${descargas?.length ?? 0} viajes registrados`}
        />
        <StatCard
          label="Camiones activos"
          value={camionesAbiertos?.length ?? 0}
          icon="🚛"
          sub={`${camionesCerrados?.length ?? 0} cerrados`}
        />
        <StatCard
          label="Silobolsas"
          value={silobolsas?.length ?? 0}
          icon="🌽"
          sub={`${silobolsas?.filter(s => !s.cerrado).length ?? 0} abiertas`}
        />
        <StatCard
          label="Clientes"
          value={clientes?.length ?? 0}
          icon="🧑‍🌾"
        />
        <StatCard
          label="Operarios"
          value={operarios?.length ?? 0}
          icon="👷"
        />
      </div>
    </div>
  )
}
