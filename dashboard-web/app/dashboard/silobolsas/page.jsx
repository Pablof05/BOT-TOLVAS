import { createAdminClient } from '../../../lib/supabase-admin'
import FiltroBar from '../../../components/FiltroBar'

function Badge({ cerrado }) {
  return cerrado
    ? <span className="px-2 py-0.5 text-xs rounded-full bg-gray-100 text-gray-500">Cerrada</span>
    : <span className="px-2 py-0.5 text-xs rounded-full bg-green-100 text-green-700 font-medium">Activa</span>
}

const GRANO_COLOR = {
  soja:    'bg-yellow-100 text-yellow-800',
  maiz:    'bg-orange-100 text-orange-800',
  trigo:   'bg-amber-100 text-amber-800',
  girasol: 'bg-yellow-200 text-yellow-900',
  sorgo:   'bg-red-100 text-red-800',
}
function GranoBadge({ grano }) {
  if (!grano) return <span className="text-gray-400">-</span>
  const color = GRANO_COLOR[grano.toLowerCase()] ?? 'bg-gray-100 text-gray-700'
  return <span className={`text-xs px-2 py-0.5 rounded-full capitalize ${color}`}>{grano}</span>
}

export default async function SilobolsasPage({ searchParams }) {
  const supabase    = createAdminClient()
  const soloActivas = searchParams?.filtro !== 'todas'
  const clienteId   = searchParams?.cliente || ''
  const campoId     = searchParams?.campo   || ''

  // Silobolsas con lote → campo → cliente
  let query = supabase
    .from('silobolsas')
    .select('id, numero, cerrado, lotes(id, nombre, grano, campos(id, nombre, cliente_id, clientes(id, nombre, apellido)))')
    .order('cerrado')
    .order('numero')
  if (soloActivas) query = query.eq('cerrado', false)
  const { data: silobolsas } = await query

  // Kg acumulado por silobolsa
  const siloIds = silobolsas?.map(s => s.id) ?? []
  const { data: descargas } = siloIds.length
    ? await supabase.from('descargas').select('silobolsa_id, kg').in('silobolsa_id', siloIds)
    : { data: [] }
  const kgPorSilo = {}
  descargas?.forEach(d => {
    kgPorSilo[d.silobolsa_id] = (kgPorSilo[d.silobolsa_id] || 0) + (d.kg || 0)
  })

  // Filtrar por cliente / campo
  const silosFiltrados = (silobolsas ?? []).filter(s => {
    const campo   = s.lotes?.campos
    const cliente = campo?.clientes
    if (clienteId && cliente?.id != clienteId) return false
    if (campoId   && campo?.id   != campoId)   return false
    return true
  })

  // Para los filtros dropdown
  const { data: clientes } = await supabase.from('clientes').select('id, nombre, apellido').order('nombre')
  const { data: campos }   = await supabase.from('campos').select('id, nombre, cliente_id').order('nombre')

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold text-gray-800">Silobolsas</h1>
        <div className="flex gap-2">
          <a href="/dashboard/silobolsas"
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition ${soloActivas ? 'bg-green-600 text-white' : 'bg-white text-gray-600 border'}`}>
            Activas
          </a>
          <a href={`/dashboard/silobolsas?filtro=todas${clienteId ? '&cliente=' + clienteId : ''}${campoId ? '&campo=' + campoId : ''}`}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition ${!soloActivas ? 'bg-green-600 text-white' : 'bg-white text-gray-600 border'}`}>
            Todas
          </a>
        </div>
      </div>

      <FiltroBar clientes={clientes ?? []} campos={campos ?? []} basePath="/dashboard/silobolsas" />

      <div className="bg-white rounded-2xl shadow overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 border-b text-xs uppercase tracking-wide bg-gray-50">
              <th className="px-4 py-3">N°</th>
              <th className="px-4 py-3">Cliente</th>
              <th className="px-4 py-3">Campo</th>
              <th className="px-4 py-3">Lote</th>
              <th className="px-4 py-3">Grano</th>
              <th className="px-4 py-3 text-right">Kg extraídos</th>
              <th className="px-4 py-3">Estado</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {!silosFiltrados.length ? (
              <tr>
                <td colSpan={7} className="text-center py-10 text-gray-400">No hay silobolsas</td>
              </tr>
            ) : silosFiltrados.map(s => {
              const lote    = s.lotes
              const campo   = lote?.campos
              const cliente = campo?.clientes
              const kg      = kgPorSilo[s.id] || 0
              return (
                <tr key={s.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-semibold">#{s.numero}</td>
                  <td className="px-4 py-3">{cliente ? `${cliente.nombre} ${cliente.apellido}` : '-'}</td>
                  <td className="px-4 py-3">{campo?.nombre ?? '-'}</td>
                  <td className="px-4 py-3">{lote?.nombre ?? '-'}</td>
                  <td className="px-4 py-3"><GranoBadge grano={lote?.grano} /></td>
                  <td className="px-4 py-3 text-right font-semibold">{kg.toLocaleString('es-AR')} kg</td>
                  <td className="px-4 py-3"><Badge cerrado={s.cerrado} /></td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
