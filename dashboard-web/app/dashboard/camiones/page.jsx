import { createAdminClient } from '../../../lib/supabase-admin'
import FiltroBar from '../../../components/FiltroBar'

function Badge({ cerrado }) {
  return cerrado
    ? <span className="px-2 py-0.5 text-xs rounded-full bg-gray-100 text-gray-500">Cerrado</span>
    : <span className="px-2 py-0.5 text-xs rounded-full bg-green-100 text-green-700 font-medium">Activo</span>
}

export default async function CamionesPage({ searchParams }) {
  const supabase    = createAdminClient()
  const soloActivos = searchParams?.filtro !== 'todos'
  const clienteId   = searchParams?.cliente || ''
  const campoId     = searchParams?.campo   || ''

  // Camiones
  let camionesQuery = supabase
    .from('camiones')
    .select('id, patente_chasis, patente_acoplado, capacidad_kg, cerrado')
    .order('cerrado')
    .order('patente_chasis')
  if (soloActivos) camionesQuery = camionesQuery.eq('cerrado', false)
  const { data: camiones } = await camionesQuery

  // Descargas con info de lote → campo → cliente
  const ids = camiones?.map(c => c.id) ?? []
  const { data: descargas } = ids.length
    ? await supabase
        .from('descargas')
        .select('camion_id, kg, lote_id, lotes(id, nombre, grano, campos(id, nombre, cliente_id, clientes(id, nombre, apellido)))')
        .in('camion_id', ids)
    : { data: [] }

  // Agregar kg y lotes únicos por camión
  const porCamion = {}
  for (const d of descargas ?? []) {
    const cid = d.camion_id
    if (!porCamion[cid]) porCamion[cid] = { kg: 0, lotes: new Map() }
    porCamion[cid].kg += d.kg || 0
    if (d.lotes && d.lote_id) porCamion[cid].lotes.set(d.lote_id, d.lotes)
  }

  // Filtrar por cliente / campo
  const camionesFiltrados = (camiones ?? []).filter(c => {
    if (!clienteId && !campoId) return true
    const lotes = [...(porCamion[c.id]?.lotes?.values() ?? [])]
    if (clienteId && !lotes.some(l => l.campos?.clientes?.id == clienteId)) return false
    if (campoId   && !lotes.some(l => l.campos?.id == campoId))             return false
    return true
  })

  // Para los filtros dropdown
  const { data: clientes } = await supabase.from('clientes').select('id, nombre, apellido').order('nombre')
  const { data: campos }   = await supabase.from('campos').select('id, nombre, cliente_id').order('nombre')

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold text-gray-800">Camiones</h1>
        <div className="flex gap-2">
          <a href="/dashboard/camiones"
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition ${soloActivos ? 'bg-green-600 text-white' : 'bg-white text-gray-600 border'}`}>
            Activos
          </a>
          <a href={`/dashboard/camiones?filtro=todos${clienteId ? '&cliente=' + clienteId : ''}${campoId ? '&campo=' + campoId : ''}`}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition ${!soloActivos ? 'bg-green-600 text-white' : 'bg-white text-gray-600 border'}`}>
            Todos
          </a>
        </div>
      </div>

      <FiltroBar clientes={clientes ?? []} campos={campos ?? []} basePath="/dashboard/camiones" />

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
              <tr>
                <td colSpan={6} className="text-center py-10 text-gray-400">No hay camiones</td>
              </tr>
            ) : camionesFiltrados.map(c => {
              const datos    = porCamion[c.id]
              const kg       = datos?.kg ?? 0
              const lotes    = datos ? [...datos.lotes.values()] : []
              return (
                <tr key={c.id} className="hover:bg-gray-50 align-top">
                  <td className="px-4 py-3 font-mono font-semibold">{c.patente_chasis}</td>
                  <td className="px-4 py-3 font-mono">{c.patente_acoplado || '-'}</td>
                  <td className="px-4 py-3">{c.capacidad_kg ? `${c.capacidad_kg.toLocaleString('es-AR')} kg` : '-'}</td>
                  <td className="px-4 py-3">
                    {lotes.length === 0 ? (
                      <span className="text-gray-400">Sin descargas</span>
                    ) : (
                      <div className="space-y-1">
                        {lotes.map(l => (
                          <div key={l.id} className="text-xs">
                            <span className="font-medium">{l.campos?.clientes?.nombre} {l.campos?.clientes?.apellido}</span>
                            <span className="text-gray-400"> · {l.campos?.nombre} · </span>
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
