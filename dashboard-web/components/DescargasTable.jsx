'use client'

import { useRouter, useSearchParams } from 'next/navigation'

function fmt(fecha) {
  if (!fecha) return '-'
  return new Date(fecha).toLocaleString('es-AR', { dateStyle: 'short', timeStyle: 'short' })
}

export default function DescargasTable({
  descargas, clientes, campos, clienteId, campoId, isCliente
}) {
  const router = useRouter()
  const params = useSearchParams()

  function setFilter(key, value) {
    const p = new URLSearchParams(params.toString())
    if (value) p.set(key, value)
    else p.delete(key)
    if (key === 'cliente') p.delete('campo')
    router.push('/dashboard/descargas?' + p.toString())
  }

  const totalKg = descargas.reduce((acc, d) => acc + (d.kg || 0), 0)
  const camposFiltrados = isCliente
    ? campos
    : campos.filter(c => !clienteId || c.cliente_id == clienteId)

  return (
    <div>
      {/* Filtros */}
      <div className="flex flex-wrap gap-3 mb-5">
        {!isCliente && (
          <select
            value={clienteId}
            onChange={e => setFilter('cliente', e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
          >
            <option value="">Todos los clientes</option>
            {clientes.map(c => (
              <option key={c.id} value={c.id}>
                {c.nombre} {c.apellido}
              </option>
            ))}
          </select>
        )}

        <select
          value={campoId}
          onChange={e => setFilter('campo', e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
        >
          <option value="">Todos los campos</option>
          {camposFiltrados.map(c => (
            <option key={c.id} value={c.id}>{c.nombre}</option>
          ))}
        </select>

        {(clienteId || campoId) && (
          <button
            onClick={() => router.push('/dashboard/descargas')}
            className="text-sm text-red-500 hover:underline"
          >
            Limpiar filtros
          </button>
        )}
      </div>

      {/* Totalizador */}
      <div className="bg-green-50 border border-green-200 rounded-xl px-4 py-3 mb-4 text-sm">
        <span className="font-semibold">{descargas.length}</span> descargas ·{' '}
        <span className="font-semibold">
          {(totalKg / 1000).toLocaleString('es-AR', { maximumFractionDigits: 1 })} t
        </span> en total
      </div>

      {/* Tabla */}
      <div className="bg-white rounded-2xl shadow overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 border-b text-xs uppercase tracking-wide bg-gray-50">
              <th className="px-4 py-3">Fecha</th>
              {!isCliente && <th className="px-4 py-3">Cliente</th>}
              <th className="px-4 py-3">Campo</th>
              <th className="px-4 py-3">Lote</th>
              <th className="px-4 py-3">Grano</th>
              <th className="px-4 py-3">Silobolsa</th>
              <th className="px-4 py-3">Camión</th>
              <th className="px-4 py-3">Operario</th>
              <th className="px-4 py-3 text-right">Kg</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {descargas.length === 0 ? (
              <tr>
                <td colSpan={isCliente ? 8 : 9} className="text-center py-10 text-gray-400">
                  No hay descargas con los filtros seleccionados
                </td>
              </tr>
            ) : (
              descargas.map(d => (
                <tr key={d.id} className="hover:bg-gray-50">
                  <td className="px-4 py-2 text-gray-500 whitespace-nowrap">{fmt(d.created_at)}</td>
                  {!isCliente && (
                    <td className="px-4 py-2">
                      {d.clientes ? `${d.clientes.nombre} ${d.clientes.apellido}` : '-'}
                    </td>
                  )}
                  <td className="px-4 py-2">{d.lotes?.campos?.nombre ?? '-'}</td>
                  <td className="px-4 py-2">{d.lotes?.nombre ?? '-'}</td>
                  <td className="px-4 py-2 capitalize">{d.lotes?.grano ?? '-'}</td>
                  <td className="px-4 py-2">{d.silobolsas ? `#${d.silobolsas.numero}` : '-'}</td>
                  <td className="px-4 py-2">{d.camiones?.patente_chasis ?? '-'}</td>
                  <td className="px-4 py-2">{d.usuarios?.nombre ?? '-'}</td>
                  <td className="px-4 py-2 text-right font-semibold">{d.kg?.toLocaleString('es-AR')}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
