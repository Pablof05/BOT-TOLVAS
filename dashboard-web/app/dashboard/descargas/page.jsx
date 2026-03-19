import { createClient } from '../../../lib/supabase-server'
import DescargasTable from '../../../components/DescargasTable'

async function getContratistaId(supabase) {
  const { data: { user } } = await supabase.auth.getUser()
  const { data } = await supabase
    .from('contratistas')
    .select('id')
    .eq('user_id', user.id)
    .single()
  return data?.id
}

export default async function DescargasPage({ searchParams }) {
  const supabase = createClient()
  const contratistaId = await getContratistaId(supabase)

  const clienteId = searchParams?.cliente || ''
  const campoId   = searchParams?.campo   || ''

  // Clientes para el filtro
  const { data: clientes } = await supabase
    .from('clientes')
    .select('id, nombre, apellido')
    .eq('contratista_id', contratistaId)
    .order('nombre')

  // Campos para el filtro (todos los del contratista)
  const { data: campos } = await supabase
    .from('campos')
    .select('id, nombre, cliente_id')
    .in('cliente_id', clientes?.map(c => c.id) ?? [])
    .order('nombre')

  // Descargas con joins
  let query = supabase
    .from('descargas')
    .select(`
      id, kg, fecha,
      camiones!inner(patente_chasis, contratista_id),
      silobolsas(numero, lotes(nombre, grano, campos(nombre, cliente_id))),
      usuarios(nombre),
      clientes(nombre, apellido)
    `)
    .eq('camiones.contratista_id', contratistaId)
    .order('fecha', { ascending: false })
    .limit(200)

  if (clienteId) query = query.eq('clientes.id', clienteId)

  const { data: descargas } = await query

  // Filtro de campo en el cliente (después de fetch)
  const descargasFiltradas = campoId
    ? descargas?.filter(d => d.silobolsas?.lotes?.campos?.id == campoId)
    : descargas

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-800 mb-6">Descargas</h1>
      <DescargasTable
        descargas={descargasFiltradas ?? []}
        clientes={clientes ?? []}
        campos={campos ?? []}
        clienteId={clienteId}
        campoId={campoId}
      />
    </div>
  )
}
