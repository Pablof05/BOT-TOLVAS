'use client'

import { useRouter, useSearchParams } from 'next/navigation'

export default function FiltroBar({ clientes = [], campos = [], lotes = [], basePath }) {
  const router = useRouter()
  const params = useSearchParams()

  const clienteId = params.get('cliente') || ''
  const campoId   = params.get('campo')   || ''
  const loteId    = params.get('lote')    || ''
  const grano     = params.get('grano')   || ''
  const desde     = params.get('desde')   || ''
  const hasta     = params.get('hasta')   || ''

  function setFilter(key, value) {
    const p = new URLSearchParams(params.toString())
    if (value) p.set(key, value)
    else p.delete(key)
    if (key === 'cliente') { p.delete('campo'); p.delete('lote'); p.delete('grano') }
    if (key === 'campo')   { p.delete('lote');  p.delete('grano') }
    if (key === 'lote')    { p.delete('grano') }
    router.push(basePath + '?' + p.toString())
  }

  const camposFiltrados = campos.filter(c => !clienteId || c.cliente_id == clienteId)
  const lotesFiltrados  = lotes.filter(l => !campoId || l.campo_id == campoId)
  const granos = [...new Set(lotesFiltrados.map(l => l.grano).filter(Boolean))].sort()

  const hayFiltros = clienteId || campoId || loteId || grano || desde || hasta

  const selectClass = "w-full sm:w-auto border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500 bg-white"

  return (
    <div className="flex flex-col sm:flex-row sm:flex-wrap gap-2 mb-5">
      {clientes.length > 0 && (
        <select value={clienteId} onChange={e => setFilter('cliente', e.target.value)} className={selectClass}>
          <option value="">Todos los clientes</option>
          {clientes.map(c => (
            <option key={c.id} value={c.id}>{c.nombre} {c.apellido}</option>
          ))}
        </select>
      )}

      {campos.length > 0 && (
        <select value={campoId} onChange={e => setFilter('campo', e.target.value)} className={selectClass}>
          <option value="">Todos los campos</option>
          {camposFiltrados.map(c => (
            <option key={c.id} value={c.id}>{c.nombre}</option>
          ))}
        </select>
      )}

      {lotes.length > 0 && (
        <select value={loteId} onChange={e => setFilter('lote', e.target.value)} className={selectClass}>
          <option value="">Todos los lotes</option>
          {lotesFiltrados.map(l => (
            <option key={l.id} value={l.id}>{l.nombre}{l.grano ? ` (${l.grano})` : ''}</option>
          ))}
        </select>
      )}

      {granos.length > 0 && (
        <select value={grano} onChange={e => setFilter('grano', e.target.value)} className={selectClass}>
          <option value="">Todos los granos</option>
          {granos.map(g => (
            <option key={g} value={g} className="capitalize">{g}</option>
          ))}
        </select>
      )}

      <div className="flex gap-2">
        <input type="date" value={desde} onChange={e => setFilter('desde', e.target.value)}
          className="flex-1 sm:flex-none border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500 bg-white" />
        <input type="date" value={hasta} onChange={e => setFilter('hasta', e.target.value)}
          className="flex-1 sm:flex-none border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500 bg-white" />
      </div>

      {hayFiltros && (
        <button onClick={() => router.push(basePath)}
          className="w-full sm:w-auto text-sm text-red-500 hover:underline py-2">
          Limpiar filtros
        </button>
      )}
    </div>
  )
}
