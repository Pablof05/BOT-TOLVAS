'use client'

import Link from 'next/link'
import { useState } from 'react'
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

export default function Sidebar({ role, profile, basePath = '/dashboard' }) {
  const pathname = usePathname()
  const router   = useRouter()
  const [open, setOpen] = useState(false)

  const baseNav  = role === 'cliente' ? navCliente : navContratista
  const navItems = baseNav.map(item => ({
    ...item,
    href: item.href.replace('/dashboard', basePath),
  }))

  async function handleLogout() {
    const supabase = createClient()
    await supabase.auth.signOut()
    router.push('/login')
    router.refresh()
  }

  const displayName = profile
    ? `${profile.nombre}${profile.apellido ? ' ' + profile.apellido : ''}`
    : ''

  const sidebarContent = (
    <>
      <div className="p-5 border-b border-green-700">
        <p className="font-bold text-lg">🌾 Tolvas</p>
        {displayName && <p className="text-green-300 text-sm mt-1 truncate">{displayName}</p>}
        {role && <span className="text-xs text-green-400 capitalize">{role}</span>}
      </div>

      <nav className="flex-1 p-3 space-y-1">
        {navItems.map(item => {
          const active = pathname === item.href || (item.href !== basePath && pathname.startsWith(item.href))
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

      <div className="p-3 border-t border-green-700">
        <button onClick={handleLogout}
          className="w-full text-left px-3 py-2 text-sm text-green-300 hover:text-white hover:bg-green-700 rounded-lg transition">
          Cerrar sesión →
        </button>
      </div>
    </>
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

      {/* Sidebar escritorio (siempre visible) */}
      <aside className="hidden md:flex w-56 bg-green-800 text-white flex-col min-h-screen shrink-0">
        {sidebarContent}
      </aside>

      {/* Sidebar móvil (drawer) */}
      <aside className={`md:hidden fixed top-0 left-0 z-50 h-full w-64 bg-green-800 text-white flex flex-col transition-transform duration-200 ${open ? 'translate-x-0' : '-translate-x-full'}`}>
        <div className="flex items-center justify-between px-4 h-14 border-b border-green-700">
          <span className="font-bold text-lg">🌾 Tolvas</span>
          <button onClick={() => setOpen(false)} className="text-green-300 text-xl">✕</button>
        </div>
        <nav className="flex-1 p-3 space-y-1">
          {navItems.map(item => {
            const active = pathname === item.href || (item.href !== basePath && pathname.startsWith(item.href))
            return (
              <Link key={item.href} href={item.href} onClick={() => setOpen(false)}
                className={`flex items-center gap-3 px-3 py-3 rounded-lg text-sm font-medium transition ${
                  active ? 'bg-green-600 text-white' : 'text-green-200 hover:bg-green-700 hover:text-white'
                }`}>
                <span>{item.icon}</span>
                {item.label}
              </Link>
            )
          })}
        </nav>
        <div className="p-3 border-t border-green-700">
          <button onClick={handleLogout}
            className="w-full text-left px-3 py-2 text-sm text-green-300 hover:text-white hover:bg-green-700 rounded-lg transition">
            Cerrar sesión →
          </button>
        </div>
      </aside>
    </>
  )
}
