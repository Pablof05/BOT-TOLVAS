import { createAdminClient } from '../../lib/supabase-admin'
import DashboardContratista from '../../components/DashboardContratista'

export default async function DashboardPage() {
  const supabase = createAdminClient()

  const [
    { data: camionesAbiertos },
    { data: camionesCerrados },
    { data: operarios },
    { data: clientes },
    { data: descargas, error },
  ] = await Promise.all([
    supabase.from('camiones').select('id, patente_chasis, patente_acoplado, capacidad_kg').eq('cerrado', false),
    supabase.from('camiones').select('id').eq('cerrado', true),
    supabase.from('usuarios').select('id').eq('rol', 'operario'),
    supabase.from('clientes').select('id'),
    supabase.from('descargas').select('kg'),
  ])

  if (error) {
    return (
      <div className="p-6 bg-red-50 rounded-xl text-red-700">
        <p className="font-semibold">Error de conexión con la base de datos</p>
        <p className="text-sm mt-1">{error.message}</p>
      </div>
    )
  }

  const ids = (camionesAbiertos ?? []).map(c => c.id)
  const { data: descargasCamiones } = ids.length
    ? await supabase.from('descargas').select('camion_id, kg').in('camion_id', ids)
    : { data: [] }

  const acumuladoPorCamion = {}
  for (const d of descargasCamiones ?? []) {
    acumuladoPorCamion[d.camion_id] = (acumuladoPorCamion[d.camion_id] ?? 0) + (d.kg || 0)
  }

  const camionesActivosData = (camionesAbiertos ?? []).map(c => ({
    ...c,
    acumulado: acumuladoPorCamion[c.id] ?? 0,
  }))

  return (
    <DashboardContratista
      camionesAbiertos={camionesAbiertos?.length ?? 0}
      camionesCerrados={camionesCerrados?.length ?? 0}
      operarios={operarios?.length ?? 0}
      clientes={clientes?.length ?? 0}
      descargas={descargas ?? []}
      camionesActivosData={camionesActivosData}
    />
  )
}
