import { createAdminClient } from '../../../../lib/supabase-admin'
import DescargasTable from '../../../../components/DescargasTable'

export default async function Page({ params, searchParams }) {
  const { codigo } = await params
  const supabase  = createAdminClient()
  const campoId   = searchParams?.campo   || ''
  const clienteId = searchParams?.cliente || ''
  const loteId    = searchParams?.lote    || ''
  const desde     = searchParams?.desde   || ''
  const hasta     = searchParams?.hasta   || ''

  const [{ data: clientes }, { data: campos }, { data: lotes }] = await Promise.all([
    supabase.from('clientes').select('id, nombre, apellido').order('nombre'),
    supabase.from('campos').select('id, nombre, cliente_id').order('nombre'),
    supabase.from('lotes').select('id, nombre, grano, campo_id').order('nombre'),
  ])

  let query = supabase
    .from('descargas')
    .select(`id, kg, created_at,
      camiones(patente_chasis), silobolsas(numero),
      lotes(nombre, grano, campos(nombre, id)),
      usuarios(nombre), clientes(nombre, apellido, id)`)
    .order('created_at', { ascending: false })
    .limit(300)

  if (clienteId) query = query.eq('cliente_id', clienteId)
  if (loteId)    query = query.eq('lote_id', loteId)
  if (desde)     query = query.gte('created_at', desde)
  if (hasta)     query = query.lte('created_at', hasta + 'T23:59:59')

  const { data: descargas } = await query

  const descargasFiltradas = campoId
    ? (descargas ?? []).filter(d => d.lotes?.campos?.id == campoId)
    : (descargas ?? [])

  const basePath = `/operario/${codigo}/descargas`

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-800 mb-6">Descargas</h1>
      <DescargasTable
        descargas={descargasFiltradas}
        clientes={clientes ?? []}
        campos={campos ?? []}
        lotes={lotes ?? []}
        clienteId={clienteId}
        campoId={campoId}
        loteId={loteId}
        desde={desde}
        hasta={hasta}
        isCliente={false}
        basePath={basePath}
      />
    </div>
  )
}
