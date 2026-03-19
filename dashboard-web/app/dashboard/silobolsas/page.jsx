import { getUserProfile } from '../../../lib/auth'
import { createClient } from '../../../lib/supabase-server'
import { redirect } from 'next/navigation'

const GRANO_COLOR = {
  soja:    'bg-yellow-100 text-yellow-800',
  maiz:    'bg-orange-100 text-orange-800',
  trigo:   'bg-amber-100 text-amber-800',
  girasol: 'bg-yellow-200 text-yellow-900',
  sorgo:   'bg-red-100 text-red-800',
}

function granoColor(g) {
  return GRANO_COLOR[g?.toLowerCase()] ?? 'bg-gray-100 text-gray-700'
}

export default async function SilobolsasPage({ searchParams }) {
  const userProfile = await getUserProfile()
  if (userProfile?.role !== 'cliente') redirect('/dashboard')

  const supabase = createClient()
  const clienteId = userProfile.profile.id
  const soloActivas = searchParams?.filtro !== 'todas'

  // Campos del cliente
  const { data: campos } = await supabase
    .from('campos')
    .select('id, nombre')
    .eq('cliente_id', clienteId)
    .order('nombre')

  const campoIds = campos?.map(c => c.id) ?? []

  // Lotes
  const { data: lotes } = campoIds.length
    ? await supabase
        .from('lotes')
        .select('id, nombre, grano, campo_id')
        .in('campo_id', campoIds)
        .order('nombre')
    : { data: [] }

  const loteIds = lotes?.map(l => l.id) ?? []

  // Silobolsas
  let siloQuery = supabase
    .from('silobolsas')
    .select('id, numero, cerrado, lote_id')
    .in('lote_id', loteIds)
    .order('numero')

  if (soloActivas) siloQuery = siloQuery.eq('cerrado', false)

  const { data: silobolsas } = loteIds.length ? await siloQuery : { data: [] }

  // Kg por silobolsa
  const siloIds = silobolsas?.map(s => s.id) ?? []
  const { data: descargas } = siloIds.length
    ? await supabase.from('descargas').select('silobolsa_id, kg').in('silobolsa_id', siloIds)
    : { data: [] }

  const kgPorSilo = {}
  descargas?.forEach(d => {
    if (d.silobolsa_id) kgPorSilo[d.silobolsa_id] = (kgPorSilo[d.silobolsa_id] || 0) + (d.kg || 0)
  })

  // Armar mapa para lookup rápido
  const loteMap = Object.fromEntries(lotes?.map(l => [l.id, l]) ?? [])
  const campoMap = Object.fromEntries(campos?.map(c => [c.id, c]) ?? [])

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-800">Silobolsas</h1>
        <div className="flex gap-2">
          <a
            href="/dashboard/silobolsas"
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition ${
              soloActivas ? 'bg-green-600 text-white' : 'bg-white text-gray-600 border'
            }`}
          >
            Activas
          </a>
          <a
            href="/dashboard/silobolsas?filtro=todas"
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition ${
              !soloActivas ? 'bg-green-600 text-white' : 'bg-white text-gray-600 border'
            }`}
          >
            Todas
          </a>
        </div>
      </div>

      <div className="bg-white rounded-2xl shadow overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-gray-400 uppercase border-b bg-gray-50">
              <th className="px-4 py-3 text-left">N°</th>
              <th className="px-4 py-3 text-left">Campo</th>
              <th className="px-4 py-3 text-left">Lote</th>
              <th className="px-4 py-3 text-left">Grano</th>
              <th className="px-4 py-3 text-right">Kg extraídos</th>
              <th className="px-4 py-3 text-left">Estado</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {!silobolsas?.length ? (
              <tr>
                <td colSpan={6} className="text-center py-10 text-gray-400">
                  No hay silobolsas {soloActivas ? 'activas' : ''}
                </td>
              </tr>
            ) : (
              silobolsas.map(s => {
                const lote  = loteMap[s.lote_id]
                const campo = lote ? campoMap[lote.campo_id] : null
                return (
                  <tr key={s.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-semibold">#{s.numero}</td>
                    <td className="px-4 py-3">{campo?.nombre ?? '-'}</td>
                    <td className="px-4 py-3">{lote?.nombre ?? '-'}</td>
                    <td className="px-4 py-3">
                      {lote?.grano ? (
                        <span className={`text-xs px-2 py-0.5 rounded-full capitalize ${granoColor(lote.grano)}`}>
                          {lote.grano}
                        </span>
                      ) : '—'}
                    </td>
                    <td className="px-4 py-3 text-right font-semibold">
                      {(kgPorSilo[s.id] || 0).toLocaleString('es-AR')} kg
                    </td>
                    <td className="px-4 py-3">
                      {s.cerrado
                        ? <span className="px-2 py-0.5 text-xs rounded-full bg-gray-100 text-gray-500">Cerrada</span>
                        : <span className="px-2 py-0.5 text-xs rounded-full bg-green-100 text-green-700 font-medium">Activa</span>
                      }
                    </td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
