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
    supabase.from('camiones').select('id').eq('cerrado', false),
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

  return (
    <DashboardContratista
      camionesAbiertos={camionesAbiertos?.length ?? 0}
      camionesCerrados={camionesCerrados?.length ?? 0}
      operarios={operarios?.length ?? 0}
      clientes={clientes?.length ?? 0}
      descargas={descargas ?? []}
    />
  )
}
