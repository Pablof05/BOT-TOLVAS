import { getUserProfile } from '../../../lib/auth'
import { createClient } from '../../../lib/supabase-server'
import DescargasTable from '../../../components/DescargasTable'

export default async function DescargasPage({ searchParams }) {
  const userProfile = await getUserProfile()
  const supabase = createClient()
  const role = userProfile?.role
  const profileId = userProfile?.profile?.id

  const campoId = searchParams?.campo || ''

  let descargas = []
  let campos = []
  let clientes = []
  let clienteId = ''

  if (role === 'cliente') {
    // Cliente: siempre sus propias descargas
    clienteId = profileId

    const { data: camposData } = await supabase
      .from('campos')
      .select('id, nombre, cliente_id')
      .eq('cliente_id', clienteId)
      .order('nombre')
    campos = camposData ?? []

    let query = supabase
      .from('descargas')
      .select(`
        id, kg, created_at,
        silobolsas(numero, lotes(nombre, grano, campos(nombre))),
        camiones(patente_chasis),
        usuarios(nombre)
      `)
      .eq('cliente_id', clienteId)
      .order('created_at', { ascending: false })
      .limit(300)

    const { data } = await query
    descargas = data ?? []

  } else {
    // Contratista: puede filtrar por cliente
    const contratistaId = profileId
    clienteId = searchParams?.cliente || ''

    const { data: clientesData } = await supabase
      .from('clientes')
      .select('id, nombre, apellido')
      .eq('contratista_id', contratistaId)
      .order('nombre')
    clientes = clientesData ?? []

    const { data: camposData } = await supabase
      .from('campos')
      .select('id, nombre, cliente_id')
      .in('cliente_id', clientes.map(c => c.id))
      .order('nombre')
    campos = camposData ?? []

    let query = supabase
      .from('descargas')
      .select(`
        id, kg, created_at,
        camiones!inner(patente_chasis, contratista_id),
        silobolsas(numero, lotes(nombre, grano, campos(nombre, id))),
        usuarios(nombre),
        clientes(nombre, apellido, id)
      `)
      .eq('camiones.contratista_id', contratistaId)
      .order('created_at', { ascending: false })
      .limit(300)

    if (clienteId) query = query.eq('cliente_id', clienteId)

    const { data } = await query
    descargas = data ?? []
  }

  // Filtro por campo (client-side después del fetch)
  const descargasFiltradas = campoId
    ? descargas.filter(d => d.silobolsas?.lotes?.campos?.id == campoId)
    : descargas

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-800 mb-6">Descargas</h1>
      <DescargasTable
        descargas={descargasFiltradas}
        clientes={clientes}
        campos={campos}
        clienteId={clienteId}
        campoId={campoId}
        isCliente={role === 'cliente'}
      />
    </div>
  )
}
