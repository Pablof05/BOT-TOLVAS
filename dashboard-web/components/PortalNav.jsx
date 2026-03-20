'use client'

import Link from 'next/link'
import { useState } from 'react'
import { usePathname } from 'next/navigation'

export default function PortalNav({ role, nombre, apellido, basePath }) {
  const pathname = usePathname()
  const [open, setOpen] = useState(false)

  const navItems = [
    { href: `${basePath}/camiones`,   label: 'Camiones',   icon: '🚛' },
    { href: `${basePath}/silobolsas`, label: 'Silobolsas', icon: '🌾' },
    { href: `${basePath}/descargas`,  label: 'Descargas',  icon: '🚜' },
  ]

  const roleLabel  = role === 'operario' ? 'Operario' : 'Cliente'
  const displayName = apellido ? `${nombre} ${apellido}` : nombre

  const navContent = (
    <nav className="flex-1 p-3 space-y-1">
      {navItems.map(item => {
        const active = pathname.startsWith(item.href)
        return (
          <Link key={item.href} href={item.href} onClick={() => setOpen(false)}
            className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition ${
              active ? 'bg-green-600 text-white' : 'text-green-200 hover:bg-green-700 hover:text-white'
            }`}>
            <span>{item.icon}</span>
            {item.label}
          </Link>
        )
      })}
    </nav>
  )

  return (
    <>
      {/* Barra superior móvil */}
      <div className="md:hidden fixed top-0 left-0 right-0 z-30 bg-green-800 text-white flex items-center px-4 h-14">
        <button onClick={() => setOpen(true)} className="text-white text-2xl mr-3">☰</button>
        <span className="font-bold text-lg">🌾 Tolvas</span>
      </div>

      {/* Overlay móvil */}
      {open && (
        <div className="md:hidden fixed inset-0 z-40 bg-black/50" onClick={() => setOpen(false)} />
      )}

      {/* Sidebar escritorio */}
      <aside className="hidden md:flex w-56 bg-green-800 text-white flex-col min-h-screen shrink-0">
        <div className="p-5 border-b border-green-700">
          <p className="font-bold text-lg">🌾 Tolvas</p>
          {displayName && <p className="text-green-300 text-sm mt-1 truncate">{displayName}</p>}
          <span className="text-xs text-green-400">{roleLabel}</span>
        </div>
        {navContent}
      </aside>

      {/* Sidebar móvil (drawer) */}
      <aside className={`md:hidden fixed top-0 left-0 z-50 h-full w-64 bg-green-800 text-white flex flex-col transition-transform duration-200 ${open ? 'translate-x-0' : '-translate-x-full'}`}>
        <div className="flex items-center justify-between px-4 h-14 border-b border-green-700">
          <div>
            <p className="font-bold">🌾 Tolvas</p>
            {displayName && <p className="text-green-300 text-xs truncate">{displayName}</p>}
          </div>
          <button onClick={() => setOpen(false)} className="text-green-300 text-xl">✕</button>
        </div>
        {navContent}
      </aside>
    </>
  )
}
