'use client'

const GRANO_COLOR = {
  soja:   'bg-yellow-100 text-yellow-800',
  maiz:   'bg-orange-100 text-orange-800',
  trigo:  'bg-amber-100 text-amber-800',
  girasol:'bg-yellow-200 text-yellow-900',
  sorgo:  'bg-red-100 text-red-800',
}

function granoColor(grano) {
  return GRANO_COLOR[grano?.toLowerCase()] ?? 'bg-gray-100 text-gray-700'
}

function fmt(fecha) {
  if (!fecha) return ''
  return new Date(fecha).toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit', year: '2-digit' })
}

export default function DashboardCliente({ campos, lotes, silobolsas, descargas, nombre }) {
  // Kg totales por grano
  const kgPorGrano = {}
  descargas.forEach(d => {
    const lote = lotes.find(l => l.id === d.lote_id)
    const grano = lote?.grano ?? 'sin grano'
    kgPorGrano[grano] = (kgPorGrano[grano] || 0) + (d.kg || 0)
  })

  // Kg por lote
  const kgPorLote = {}
  descargas.forEach(d => {
    if (d.lote_id) kgPorLote[d.lote_id] = (kgPorLote[d.lote_id] || 0) + (d.kg || 0)
  })

  // Kg por silobolsa
  const kgPorSilo = {}
  descargas.forEach(d => {
    if (d.silobolsa_id) kgPorSilo[d.silobolsa_id] = (kgPorSilo[d.silobolsa_id] || 0) + (d.kg || 0)
  })

  const totalKg = descargas.reduce((acc, d) => acc + (d.kg || 0), 0)
  const silosActivos = silobolsas.filter(s => !s.cerrado).length

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-800 mb-1">Bienvenido, {nombre}</h1>
      <p className="text-gray-500 text-sm mb-6">Resumen de tu grano</p>

      {/* Resumen por grano */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
        <div className="bg-white rounded-2xl shadow p-4 col-span-2 md:col-span-1">
          <p className="text-xs text-gray-500 mb-1">Total extraído</p>
          <p className="text-3xl font-bold text-green-700">
            {(totalKg / 1000).toLocaleString('es-AR', { maximumFractionDigits: 1 })} t
          </p>
          <p className="text-xs text-gray-400 mt-1">{descargas.length} descargas</p>
        </div>

        {Object.entries(kgPorGrano).map(([grano, kg]) => (
          <div key={grano} className="bg-white rounded-2xl shadow p-4">
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium capitalize ${granoColor(grano)}`}>
              {grano}
            </span>
            <p className="text-2xl font-bold text-gray-800 mt-2">
              {(kg / 1000).toLocaleString('es-AR', { maximumFractionDigits: 1 })} t
            </p>
          </div>
        ))}

        <div className="bg-white rounded-2xl shadow p-4">
          <p className="text-xs text-gray-500 mb-1">Silobolsas activas</p>
          <p className="text-3xl font-bold text-gray-800">{silosActivos}</p>
          <p className="text-xs text-gray-400 mt-1">de {silobolsas.length} totales</p>
        </div>
      </div>

      {/* Campos expandibles */}
      <h2 className="text-lg font-semibold text-gray-700 mb-3">Mis campos</h2>
      <div className="space-y-4">
        {campos.length === 0 && (
          <p className="text-gray-400 text-sm">No hay campos registrados.</p>
        )}
        {campos.map(campo => {
          const lotesDelCampo = lotes.filter(l => l.campo_id === campo.id)
          const kgCampo = lotesDelCampo.reduce((acc, l) => acc + (kgPorLote[l.id] || 0), 0)

          return (
            <div key={campo.id} className="bg-white rounded-2xl shadow overflow-hidden">
              <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
                <h3 className="font-semibold text-gray-800">{campo.nombre}</h3>
                <span className="text-sm text-gray-500">
                  {(kgCampo / 1000).toLocaleString('es-AR', { maximumFractionDigits: 1 })} t extraídas
                </span>
              </div>

              {lotesDelCampo.length === 0 ? (
                <p className="px-5 py-3 text-sm text-gray-400">Sin lotes</p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-xs text-gray-400 uppercase border-b bg-gray-50">
                      <th className="px-5 py-2 text-left">Lote</th>
                      <th className="px-5 py-2 text-left">Grano</th>
                      <th className="px-5 py-2 text-right">Kg extraídos</th>
                      <th className="px-5 py-2 text-right">Silobolsas</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {lotesDelCampo.map(lote => {
                      const silosLote = silobolsas.filter(s => s.lote_id === lote.id)
                      const silosActivos = silosLote.filter(s => !s.cerrado).length
                      return (
                        <tr key={lote.id} className="hover:bg-gray-50">
                          <td className="px-5 py-3 font-medium">{lote.nombre}</td>
                          <td className="px-5 py-3">
                            {lote.grano ? (
                              <span className={`text-xs px-2 py-0.5 rounded-full capitalize ${granoColor(lote.grano)}`}>
                                {lote.grano}
                              </span>
                            ) : (
                              <span className="text-gray-300 text-xs">—</span>
                            )}
                          </td>
                          <td className="px-5 py-3 text-right font-semibold">
                            {(kgPorLote[lote.id] || 0).toLocaleString('es-AR')} kg
                          </td>
                          <td className="px-5 py-3 text-right text-gray-500">
                            {silosActivos} activas / {silosLote.length}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              )}
            </div>
          )
        })}
      </div>

      {/* Últimas descargas */}
      {descargas.length > 0 && (
        <div className="mt-8">
          <h2 className="text-lg font-semibold text-gray-700 mb-3">Últimas descargas</h2>
          <div className="bg-white rounded-2xl shadow overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-gray-400 uppercase border-b bg-gray-50">
                  <th className="px-4 py-3 text-left">Fecha</th>
                  <th className="px-4 py-3 text-left">Grano</th>
                  <th className="px-4 py-3 text-right">Kg</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {descargas.slice(0, 10).map((d, i) => {
                  const lote = lotes.find(l => l.id === d.lote_id)
                  return (
                    <tr key={i} className="hover:bg-gray-50">
                      <td className="px-4 py-2 text-gray-500">{fmt(d.created_at)}</td>
                      <td className="px-4 py-2">
                        {lote?.grano ? (
                          <span className={`text-xs px-2 py-0.5 rounded-full capitalize ${granoColor(lote.grano)}`}>
                            {lote.grano}
                          </span>
                        ) : '—'}
                      </td>
                      <td className="px-4 py-2 text-right font-semibold">{d.kg?.toLocaleString('es-AR')}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
