import { getUserProfile } from '../../lib/auth'
import { createClient } from '../../lib/supabase-server'
import DashboardContratista from '../../components/DashboardContratista'
import DashboardCliente from '../../components/DashboardCliente'

export default async function DashboardPage() {
  const userProfile = await getUserProfile()
  const supabase = createClient()

  if (userProfile?.role === 'cliente') {
    const clienteId = userProfile.profile.id

    // Campos del cliente
    const { data: campos } = await supabase
      .from('campos')
      .select('id, nombre')
      .eq('cliente_id', clienteId)
      .order('nombre')

    const campoIds = campos?.map(c => c.id) ?? []

    // Lotes con grano
    const { data: lotes } = campoIds.length
      ? await supabase
          .from('lotes')
          .select('id, nombre, grano, campo_id')
          .in('campo_id', campoIds)
          .order('nombre')
      : { data: [] }

    const loteIds = lotes?.map(l => l.id) ?? []

    // Silobolsas
    const { data: silobolsas } = loteIds.length
      ? await supabase
          .from('silobolsas')
          .select('id, numero, cerrado, lote_id')
          .in('lote_id', loteIds)
      : { data: [] }

    // Descargas del cliente (kg por silobolsa y por lote)
    const { data: descargas } = await supabase
      .from('descargas')
      .select('kg, lote_id, campo_id, silobolsa_id, created_at')
      .eq('cliente_id', clienteId)
      .order('created_at', { ascending: false })

    return (
      <DashboardCliente
        campos={campos ?? []}
        lotes={lotes ?? []}
        silobolsas={silobolsas ?? []}
        descargas={descargas ?? []}
        nombre={userProfile.profile.nombre}
      />
    )
  }

  // Vista contratista
  const contratistaId = userProfile?.profile?.id
  if (!contratistaId) {
    return (
      <div className="text-center py-20 text-gray-500">
        <p>No hay contratista vinculado a tu cuenta.</p>
      </div>
    )
  }

  const [
    { data: camionesAbiertos },
    { data: camionesCerrados },
    { data: operarios },
    { data: clientes },
    { data: descargas },
  ] = await Promise.all([
    supabase.from('camiones').select('id').eq('contratista_id', contratistaId).eq('cerrado', false),
    supabase.from('camiones').select('id').eq('contratista_id', contratistaId).eq('cerrado', true),
    supabase.from('usuarios').select('id').eq('contratista_id', contratistaId).eq('rol', 'operario'),
    supabase.from('clientes').select('id').eq('contratista_id', contratistaId),
    supabase.from('descargas').select('kg').eq('contratista_id', contratistaId),
  ])

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
