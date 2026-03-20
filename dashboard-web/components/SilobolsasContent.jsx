import { createAdminClient } from '../lib/supabase-admin'
import FiltroBar from './FiltroBar'

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

export default async function SilobolsasContent({ basePath, searchParams, fixedClienteId = null, allowedClienteIds = null }) {
  const supabase    = createAdminClient()
  const soloActivas = searchParams?.filtro !== 'todas'
  const clienteId   = searchParams?.cliente || ''
  const campoId     = searchParams?.campo   || ''
  const loteId      = searchParams?.lote    || ''
  const grano       = searchParams?.grano   || ''
  const desde       = searchParams?.desde   || ''
  const hasta       = searchParams?.hasta   || ''

  let query = supabase
    .from('silobolsas')
    .select('id, numero, cerrado, lotes(id, nombre, grano, campos(id, nombre, cliente_id, clientes(id, nombre, apellido)))')
    .order('cerrado')
    .order('numero')
  if (soloActivas) query = query.eq('cerrado', false)
  if (fixedClienteId) query = query.eq('lotes.campos.cliente_id', fixedClienteId)
  const { data: silobolsas } = await query

  const siloIds = silobolsas?.map(s => s.id) ?? []
  let descQuery = siloIds.length
    ? supabase.from('descargas').select('silobolsa_id, kg, created_at').in('silobolsa_id', siloIds)
    : null
  if (descQuery && desde) descQuery = descQuery.gte('created_at', desde)
  if (descQuery && hasta) descQuery = descQuery.lte('created_at', hasta + 'T23:59:59')
  const { data: descargas } = descQuery ? await descQuery : { data: [] }

  const kgPorSilo = {}
  descargas?.forEach(d => {
    kgPorSilo[d.silobolsa_id] = (kgPorSilo[d.silobolsa_id] || 0) + (d.kg || 0)
  })

  // Filtrar client-side (join anidado no soporta eq directo en supabase)
  const silosBase = fixedClienteId
    ? (silobolsas ?? []).filter(s => s.lotes?.campos?.clientes?.id == fixedClienteId)
    : allowedClienteIds?.length
      ? (silobolsas ?? []).filter(s => allowedClienteIds.includes(s.lotes?.campos?.clientes?.id))
      : (silobolsas ?? [])

  const clientesMap = new Map()
  const camposMap   = new Map()
  const lotesMap    = new Map()
  for (const s of silosBase) {
    const lote    = s.lotes
    const campo   = lote?.campos
    const cliente = campo?.clientes
    if (cliente) clientesMap.set(cliente.id, cliente)
    if (campo)   camposMap.set(campo.id, { id: campo.id, nombre: campo.nombre, cliente_id: campo.cliente_id })
    if (lote)    lotesMap.set(lote.id, { id: lote.id, nombre: lote.nombre, grano: lote.grano, campo_id: campo?.id })
  }
  const clientesList = [...clientesMap.values()]
    .filter(c => !allowedClienteIds || allowedClienteIds.includes(c.id))
    .sort((a, b) => a.nombre.localeCompare(b.nombre))
  const camposList   = [...camposMap.values()].sort((a, b) => a.nombre.localeCompare(b.nombre))
  const lotesList    = [...lotesMap.values()].sort((a, b) => a.nombre.localeCompare(b.nombre))

  const silosFiltrados = silosBase.filter(s => {
    const lote    = s.lotes
    const campo   = lote?.campos
    const cliente = campo?.clientes
    if (clienteId && cliente?.id != clienteId)                          return false
    if (campoId   && campo?.id   != campoId)                            return false
    if (loteId    && lote?.id    != loteId)                             return false
    if (grano     && lote?.grano?.toLowerCase() != grano.toLowerCase()) return false
    return true
  })

  const filtroHref = (extra) => {
    const p = new URLSearchParams()
    if (clienteId) p.set('cliente', clienteId)
    if (campoId)   p.set('campo', campoId)
    if (loteId)    p.set('lote', loteId)
    if (grano)     p.set('grano', grano)
    if (desde)     p.set('desde', desde)
    if (hasta)     p.set('hasta', hasta)
    Object.entries(extra).forEach(([k, v]) => v ? p.set(k, v) : p.delete(k))
    const s = p.toString()
    return basePath + (s ? '?' + s : '')
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold text-gray-800">Silobolsas</h1>
        <div className="flex gap-2">
          <a href={filtroHref({ filtro: '' })}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition ${soloActivas ? 'bg-green-600 text-white' : 'bg-white text-gray-600 border'}`}>
            Activas
          </a>
          <a href={filtroHref({ filtro: 'todas' })}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition ${!soloActivas ? 'bg-green-600 text-white' : 'bg-white text-gray-600 border'}`}>
            Todas
          </a>
        </div>
      </div>

      <FiltroBar
        clientes={fixedClienteId ? [] : clientesList}
        campos={camposList}
        lotes={lotesList}
        basePath={basePath}
      />

      <div className="bg-white rounded-2xl shadow overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 border-b text-xs uppercase tracking-wide bg-gray-50">
              <th className="px-4 py-3">N°</th>
              {!fixedClienteId && <th className="px-4 py-3">Cliente</th>}
              <th className="px-4 py-3">Campo</th>
              <th className="px-4 py-3">Lote</th>
              <th className="px-4 py-3">Grano</th>
              <th className="px-4 py-3 text-right">Kg extraídos</th>
              <th className="px-4 py-3">Estado</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {!silosFiltrados.length ? (
              <tr><td colSpan={fixedClienteId ? 6 : 7} className="text-center py-10 text-gray-400">No hay silobolsas</td></tr>
            ) : silosFiltrados.map(s => {
              const lote    = s.lotes
              const campo   = lote?.campos
              const cliente = campo?.clientes
              return (
                <tr key={s.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-semibold">#{s.numero}</td>
                  {!fixedClienteId && <td className="px-4 py-3">{cliente ? `${cliente.nombre} ${cliente.apellido}` : '-'}</td>}
                  <td className="px-4 py-3">{campo?.nombre ?? '-'}</td>
                  <td className="px-4 py-3">{lote?.nombre ?? '-'}</td>
                  <td className="px-4 py-3"><GranoBadge grano={lote?.grano} /></td>
                  <td className="px-4 py-3 text-right font-semibold">{(kgPorSilo[s.id] || 0).toLocaleString('es-AR')} kg</td>
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
