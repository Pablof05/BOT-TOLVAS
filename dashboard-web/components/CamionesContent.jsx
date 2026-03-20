import { createAdminClient } from '../lib/supabase-admin'
import FiltroBar from './FiltroBar'

function Badge({ cerrado }) {
  return cerrado
    ? <span className="px-2 py-0.5 text-xs rounded-full bg-gray-100 text-gray-500">Cerrado</span>
    : <span className="px-2 py-0.5 text-xs rounded-full bg-green-100 text-green-700 font-medium">Activo</span>
}

export default async function CamionesContent({ basePath, searchParams, fixedClienteId = null, allowedClienteIds = null }) {
  const supabase    = createAdminClient()
  const soloActivos = searchParams?.filtro !== 'todos'
  const clienteId   = searchParams?.cliente || ''
  const campoId     = searchParams?.campo   || ''
  const loteId      = searchParams?.lote    || ''
  const grano       = searchParams?.grano   || ''
  const desde       = searchParams?.desde   || ''
  const hasta       = searchParams?.hasta   || ''

  let camionesQuery = supabase
    .from('camiones')
    .select('id, patente_chasis, patente_acoplado, capacidad_kg, cerrado')
    .order('cerrado')
    .order('patente_chasis')
  if (soloActivos) camionesQuery = camionesQuery.eq('cerrado', false)
  const { data: camiones } = await camionesQuery

  const ids = camiones?.map(c => c.id) ?? []
  let descQuery = ids.length
    ? supabase
        .from('descargas')
        .select('camion_id, kg, lote_id, created_at, lotes(id, nombre, grano, campos(id, nombre, cliente_id, clientes(id, nombre, apellido)))')
        .in('camion_id', ids)
    : null
  if (descQuery && fixedClienteId)            descQuery = descQuery.eq('cliente_id', fixedClienteId)
  if (descQuery && allowedClienteIds?.length) descQuery = descQuery.in('cliente_id', allowedClienteIds)
  if (descQuery && desde) descQuery = descQuery.gte('created_at', desde)
  if (descQuery && hasta) descQuery = descQuery.lte('created_at', hasta + 'T23:59:59')
  const { data: descargas } = descQuery ? await descQuery : { data: [] }

  const porCamion = {}
  for (const d of descargas ?? []) {
    const cid = d.camion_id
    if (!porCamion[cid]) porCamion[cid] = { kg: 0, lotes: new Map() }
    porCamion[cid].kg += d.kg || 0
    if (d.lotes && d.lote_id) porCamion[cid].lotes.set(d.lote_id, d.lotes)
  }

  const clientesMap = new Map()
  const camposMap   = new Map()
  const lotesMap    = new Map()
  for (const datos of Object.values(porCamion)) {
    for (const l of datos.lotes.values()) {
      if (l.campos?.clientes) clientesMap.set(l.campos.clientes.id, l.campos.clientes)
      if (l.campos)           camposMap.set(l.campos.id, { id: l.campos.id, nombre: l.campos.nombre, cliente_id: l.campos.cliente_id })
      lotesMap.set(l.id, { id: l.id, nombre: l.nombre, grano: l.grano, campo_id: l.campos?.id })
    }
  }
  const clientesList = [...clientesMap.values()]
    .filter(c => !allowedClienteIds || allowedClienteIds.includes(c.id))
    .sort((a, b) => a.nombre.localeCompare(b.nombre))
  const camposList   = [...camposMap.values()].sort((a, b) => a.nombre.localeCompare(b.nombre))
  const lotesList    = [...lotesMap.values()].sort((a, b) => a.nombre.localeCompare(b.nombre))

  const camionesFiltrados = (camiones ?? []).filter(c => {
    const lotes = [...(porCamion[c.id]?.lotes?.values() ?? [])]
    if (clienteId && !lotes.some(l => l.campos?.clientes?.id == clienteId)) return false
    if (campoId   && !lotes.some(l => l.campos?.id == campoId))             return false
    if (loteId    && !lotes.some(l => l.id == loteId))                      return false
    if (grano     && !lotes.some(l => l.grano?.toLowerCase() == grano.toLowerCase())) return false
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
        <h1 className="text-2xl font-bold text-gray-800">Camiones</h1>
        <div className="flex gap-2">
          <a href={filtroHref({ filtro: '' })}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition ${soloActivos ? 'bg-green-600 text-white' : 'bg-white text-gray-600 border'}`}>
            Activos
          </a>
          <a href={filtroHref({ filtro: 'todos' })}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition ${!soloActivos ? 'bg-green-600 text-white' : 'bg-white text-gray-600 border'}`}>
            Todos
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
              <th className="px-4 py-3">Chasis</th>
              <th className="px-4 py-3">Acoplado</th>
              <th className="px-4 py-3">Capacidad</th>
              <th className="px-4 py-3">Cliente / Campo / Lote</th>
              <th className="px-4 py-3 text-right">Kg cargados</th>
              <th className="px-4 py-3">Estado</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {!camionesFiltrados.length ? (
              <tr><td colSpan={6} className="text-center py-10 text-gray-400">No hay camiones</td></tr>
            ) : camionesFiltrados.map(c => {
              const datos = porCamion[c.id]
              const kg    = datos?.kg ?? 0
              const lotes = datos ? [...datos.lotes.values()] : []
              return (
                <tr key={c.id} className="hover:bg-gray-50 align-top">
                  <td className="px-4 py-3 font-mono font-semibold">{c.patente_chasis}</td>
                  <td className="px-4 py-3 font-mono">{c.patente_acoplado || '-'}</td>
                  <td className="px-4 py-3">{c.capacidad_kg ? `${c.capacidad_kg.toLocaleString('es-AR')} kg` : '-'}</td>
                  <td className="px-4 py-3">
                    {lotes.length === 0 ? (
                      <span className="text-gray-400">Sin descargas{desde || hasta ? ' en el período' : ''}</span>
                    ) : (
                      <div className="space-y-1">
                        {lotes.map(l => (
                          <div key={l.id} className="text-xs">
                            {!fixedClienteId && (
                              <span className="font-medium">{l.campos?.clientes?.nombre} {l.campos?.clientes?.apellido} · </span>
                            )}
                            <span className="text-gray-600">{l.campos?.nombre} · </span>
                            <span>{l.nombre}</span>
                            {l.grano && <span className="ml-1 text-gray-400 capitalize">({l.grano})</span>}
                          </div>
                        ))}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right font-semibold">{kg.toLocaleString('es-AR')} kg</td>
                  <td className="px-4 py-3"><Badge cerrado={c.cerrado} /></td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
