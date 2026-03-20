'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { createClient } from '../lib/supabase'

const navContratista = [
  { href: '/dashboard',              label: 'Resumen',    icon: '📊' },
  { href: '/dashboard/descargas',    label: 'Descargas',  icon: '🚜' },
  { href: '/dashboard/camiones',     label: 'Camiones',   icon: '🚛' },
  { href: '/dashboard/silobolsas',   label: 'Silobolsas', icon: '🌾' },
  { href: '/dashboard/usuarios',     label: 'Usuarios',   icon: '👥' },
]

const navCliente = [
  { href: '/dashboard',              label: 'Mis campos',  icon: '🌾' },
  { href: '/dashboard/silobolsas',   label: 'Silobolsas', icon: '🌽' },
  { href: '/dashboard/descargas',    label: 'Descargas',  icon: '🚜' },
]

export default function Sidebar({ role, profile }) {
  const pathname = usePathname()
  const router = useRouter()

  const navItems = role === 'cliente' ? navCliente : navContratista

  async function handleLogout() {
    const supabase = createClient()
    await supabase.auth.signOut()
    router.push('/login')
    router.refresh()
  }

  const displayName = profile
    ? `${profile.nombre}${profile.apellido ? ' ' + profile.apellido : ''}`
    : ''

  return (
    <aside className="w-56 bg-green-800 text-white flex flex-col min-h-screen shrink-0">
      <div className="p-5 border-b border-green-700">
        <p className="font-bold text-lg">🌾 Tolvas</p>
        {displayName && (
          <p className="text-green-300 text-sm mt-1 truncate">{displayName}</p>
        )}
        {role && (
          <span className="text-xs text-green-400 capitalize">{role}</span>
        )}
      </div>

      <nav className="flex-1 p-3 space-y-1">
        {navItems.map(item => {
          const active = pathname === item.href
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

      <div className="p-3 border-t border-green-700">
        <button
          onClick={handleLogout}
          className="w-full text-left px-3 py-2 text-sm text-green-300 hover:text-white hover:bg-green-700 rounded-lg transition"
        >
          Cerrar sesión →
        </button>
      </div>
    </aside>
  )
}
