import { createAdminClient } from '../../../lib/supabase-admin'
import DescargasTable from '../../../components/DescargasTable'

export default async function DescargasPage({ searchParams }) {
  const supabase = createAdminClient()
  const campoId = searchParams?.campo || ''
  const clienteId = searchParams?.cliente || ''

  const { data: clientes, error: errCl } = await supabase
    .from('clientes')
    .select('id, nombre, apellido')
    .order('nombre')

  if (errCl) {
    return (
      <div className="p-6 bg-red-50 rounded-xl text-red-700">
        <p className="font-semibold">Error de conexión con la base de datos</p>
        <p className="text-sm mt-1">{errCl.message}</p>
        <p className="text-xs mt-2 text-red-500">Verificá que SUPABASE_SERVICE_ROLE_KEY esté configurada en Vercel.</p>
      </div>
    )
  }

  const { data: campos } = await supabase
    .from('campos')
    .select('id, nombre, cliente_id')
    .order('nombre')

  let query = supabase
    .from('descargas')
    .select(`
      id, kg, created_at,
      camiones(patente_chasis),
      silobolsas(numero, lotes(nombre, grano, campos(nombre, id))),
      usuarios(nombre),
      clientes(nombre, apellido, id)
    `)
    .order('created_at', { ascending: false })
    .limit(300)

  if (clienteId) query = query.eq('cliente_id', clienteId)

  const { data: descargas } = await query

  const descargasFiltradas = campoId
    ? (descargas ?? []).filter(d => d.silobolsas?.lotes?.campos?.id == campoId)
    : (descargas ?? [])

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-800 mb-6">Descargas</h1>
      <DescargasTable
        descargas={descargasFiltradas}
        clientes={clientes ?? []}
        campos={campos ?? []}
        clienteId={clienteId}
        campoId={campoId}
        isCliente={false}
      />
    </div>
  )
}
