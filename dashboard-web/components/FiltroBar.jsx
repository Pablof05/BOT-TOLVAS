'use client'

import { useRouter, useSearchParams } from 'next/navigation'

export default function FiltroBar({ clientes, campos, basePath }) {
  const router = useRouter()
  const params = useSearchParams()

  const clienteId = params.get('cliente') || ''
  const campoId   = params.get('campo')   || ''

  function setFilter(key, value) {
    const p = new URLSearchParams(params.toString())
    if (value) p.set(key, value)
    else p.delete(key)
    if (key === 'cliente') p.delete('campo')
    router.push(basePath + '?' + p.toString())
  }

  const camposFiltrados = campos.filter(c => !clienteId || c.cliente_id == clienteId)

  return (
    <div className="flex flex-wrap gap-3 mb-5">
      <select
        value={clienteId}
        onChange={e => setFilter('cliente', e.target.value)}
        className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
      >
        <option value="">Todos los clientes</option>
        {clientes.map(c => (
          <option key={c.id} value={c.id}>{c.nombre} {c.apellido}</option>
        ))}
      </select>

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
          onClick={() => router.push(basePath)}
          className="text-sm text-red-500 hover:underline"
        >
          Limpiar filtros
        </button>
      )}
    </div>
  )
}
