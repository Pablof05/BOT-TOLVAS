'use client'

import { useState } from 'react'

export default function CopiarLink({ url }) {
  const [copiado, setCopiado] = useState(false)

  async function copiar() {
    await navigator.clipboard.writeText(url)
    setCopiado(true)
    setTimeout(() => setCopiado(false), 2000)
  }

  return (
    <button
      onClick={copiar}
      className="text-xs px-2 py-1 rounded bg-green-100 text-green-700 hover:bg-green-200 transition"
    >
      {copiado ? 'Copiado!' : 'Copiar link'}
    </button>
  )
}
