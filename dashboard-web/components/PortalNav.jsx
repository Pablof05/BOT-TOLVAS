'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'

export default function PortalNav({ role, nombre, apellido, basePath }) {
  const pathname = usePathname()

  const navItems = [
    { href: `${basePath}/camiones`,   label: 'Camiones',   icon: '🚛' },
    { href: `${basePath}/silobolsas`, label: 'Silobolsas', icon: '🌾' },
    { href: `${basePath}/descargas`,  label: 'Descargas',  icon: '🚜' },
  ]

  const roleLabel = role === 'operario' ? 'Operario' : 'Cliente'
  const displayName = apellido ? `${nombre} ${apellido}` : nombre

  return (
    <aside className="w-56 bg-green-800 text-white flex flex-col min-h-screen shrink-0">
      <div className="p-5 border-b border-green-700">
        <p className="font-bold text-lg">🌾 Tolvas</p>
        {displayName && (
          <p className="text-green-300 text-sm mt-1 truncate">{displayName}</p>
        )}
        <span className="text-xs text-green-400">{roleLabel}</span>
      </div>

      <nav className="flex-1 p-3 space-y-1">
        {navItems.map(item => {
          const active = pathname.startsWith(item.href)
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition ${
                active
                  ? 'bg-green-600 text-white'
                  : 'text-green-200 hover:bg-green-700 hover:text-white'
              }`}
            >
              <span>{item.icon}</span>
              {item.label}
            </Link>
          )
        })}
      </nav>
    </aside>
  )
}
