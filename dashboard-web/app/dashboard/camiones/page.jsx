import { createClient } from '../../../lib/supabase-server'

async function getContratistaId(supabase) {
  const { data: { user } } = await supabase.auth.getUser()
  const { data } = await supabase
    .from('contratistas')
    .select('id')
    .eq('user_id', user.id)
    .single()
  return data?.id
}

function Badge({ cerrado }) {
  return cerrado
    ? <span className="px-2 py-0.5 text-xs rounded-full bg-gray-100 text-gray-500">Cerrado</span>
    : <span className="px-2 py-0.5 text-xs rounded-full bg-green-100 text-green-700 font-medium">Activo</span>
}

export default async function CamionesPage({ searchParams }) {
  const supabase = createClient()
  const contratistaId = await getContratistaId(supabase)

  const soloActivos = searchParams?.filtro !== 'todos'

  let query = supabase
    .from('camiones')
    .select('id, patente_chasis, patente_acoplado, capacidad_kg, cerrado')
    .eq('contratista_id', contratistaId)
    .order('cerrado')
    .order('patente_chasis')

  if (soloActivos) query = query.eq('cerrado', false)

  const { data: camiones } = await query

  // Kg cargados por camión
  const ids = camiones?.map(c => c.id) ?? []
  const { data: descargas } = ids.length
    ? await supabase.from('descargas').select('camion_id, kg').in('camion_id', ids)
    : { data: [] }

  const kgPorCamion = {}
  descargas?.forEach(d => {
    kgPorCamion[d.camion_id] = (kgPorCamion[d.camion_id] || 0) + (d.kg || 0)
  })

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-800">Camiones</h1>
        <div className="flex gap-2">
          <a
            href="/dashboard/camiones"
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition ${
              soloActivos ? 'bg-green-600 text-white' : 'bg-white text-gray-600 border'
            }`}
          >
            Activos
          </a>
          <a
            href="/dashboard/camiones?filtro=todos"
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition ${
              !soloActivos ? 'bg-green-600 text-white' : 'bg-white text-gray-600 border'
            }`}
          >
            Todos
          </a>
        </div>
      </div>

      <div className="bg-white rounded-2xl shadow overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 border-b text-xs uppercase tracking-wide">
              <th className="px-4 py-3">Chasis</th>
              <th className="px-4 py-3">Acoplado</th>
              <th className="px-4 py-3">Capacidad</th>
              <th className="px-4 py-3 text-right">Kg cargados</th>
              <th className="px-4 py-3">Estado</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {!camiones?.length ? (
              <tr>
                <td colSpan={5} className="text-center py-10 text-gray-400">
                  No hay camiones
                </td>
              </tr>
            ) : (
              camiones.map(c => (
                <tr key={c.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-mono font-semibold">{c.patente_chasis}</td>
                  <td className="px-4 py-3 font-mono">{c.patente_acoplado || '-'}</td>
                  <td className="px-4 py-3">{c.capacidad_kg ? `${c.capacidad_kg.toLocaleString('es-AR')} kg` : '-'}</td>
                  <td className="px-4 py-3 text-right font-semibold">
                    {(kgPorCamion[c.id] || 0).toLocaleString('es-AR')} kg
                  </td>
                  <td className="px-4 py-3"><Badge cerrado={c.cerrado} /></td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
