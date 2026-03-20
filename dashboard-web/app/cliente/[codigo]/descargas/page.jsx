import { createAdminClient } from '../../../../lib/supabase-admin'
import { notFound } from 'next/navigation'
import DescargasTable from '../../../../components/DescargasTable'

export default async function Page({ params, searchParams }) {
  const { codigo } = await params
  const supabase  = createAdminClient()

  const { data: cliente } = await supabase
    .from('clientes')
    .select('id')
    .eq('codigo_acceso', codigo)
    .single()

  if (!cliente) notFound()

  const clienteId = cliente.id
  const campoId   = searchParams?.campo  || ''
  const loteId    = searchParams?.lote   || ''
  const desde     = searchParams?.desde  || ''
  const hasta     = searchParams?.hasta  || ''

  const { data: campos } = await supabase
    .from('campos').select('id, nombre, cliente_id').eq('cliente_id', clienteId).order('nombre')

  const campoIds = (campos ?? []).map(c => c.id)
  const { data: lotes } = campoIds.length
    ? await supabase.from('lotes').select('id, nombre, grano, campo_id').in('campo_id', campoIds).order('nombre')
    : { data: [] }

  let query = supabase
    .from('descargas')
    .select(`id, kg, created_at,
      camiones(patente_chasis), silobolsas(numero),
      lotes(nombre, grano, campos(nombre, id)),
      usuarios(nombre), clientes(nombre, apellido, id)`)
    .eq('cliente_id', clienteId)
    .order('created_at', { ascending: false })
    .limit(300)

  if (loteId) query = query.eq('lote_id', loteId)
  if (desde)  query = query.gte('created_at', desde)
  if (hasta)  query = query.lte('created_at', hasta + 'T23:59:59')

  const { data: descargas } = await query

  const descargasFiltradas = campoId
    ? (descargas ?? []).filter(d => d.lotes?.campos?.id == campoId)
    : (descargas ?? [])

  const basePath = `/cliente/${codigo}/descargas`

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-800 mb-6">Descargas</h1>
      <DescargasTable
        descargas={descargasFiltradas}
        clientes={[]}
        campos={campos ?? []}
        lotes={lotes ?? []}
        clienteId=""
        campoId={campoId}
        loteId={loteId}
        desde={desde}
        hasta={hasta}
        isCliente={true}
        basePath={basePath}
      />
    </div>
  )
}
