'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { createClient } from '../../lib/supabase'
import Link from 'next/link'

export default function RegisterPage() {
  const router = useRouter()

  // Paso 1: telegram_id
  const [telegramId, setTelegramId] = useState('')
  const [perfil, setPerfil] = useState(null) // { tipo, ref_id, nombre }
  const [paso, setPaso] = useState(1)

  // Paso 2: email + password
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleValidarTelegram(e) {
    e.preventDefault()
    setLoading(true)
    setError('')

    const res = await fetch('/api/validate-telegram', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ telegram_id: telegramId }),
    })
    const data = await res.json()
    setLoading(false)

    if (!res.ok) {
      setError(data.error)
      return
    }

    setPerfil(data)
    setPaso(2)
  }

  async function handleRegistrar(e) {
    e.preventDefault()
    setError('')

    if (password !== confirm) {
      setError('Las contraseñas no coinciden')
      return
    }

    setLoading(true)

    const res = await fetch('/api/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        telegram_id: telegramId,
        tipo: perfil.tipo,
        ref_id: perfil.ref_id,
        email,
        password,
      }),
    })
    const data = await res.json()

    if (!res.ok) {
      setError(data.error)
      setLoading(false)
      return
    }

    // Login automático
    const supabase = createClient()
    const { error: loginError } = await supabase.auth.signInWithPassword({ email, password })

    if (loginError) {
      setLoading(false)
      setError('Cuenta creada. Podés iniciar sesión desde el login.')
      return
    }

    window.location.href = '/dashboard'
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-green-50">
      <div className="bg-white rounded-2xl shadow-lg p-8 w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-green-700">🌾 Tolvas</h1>
          <p className="text-gray-500 mt-1 text-sm">Crear cuenta en el panel</p>
        </div>

        {paso === 1 && (
          <form onSubmit={handleValidarTelegram} className="space-y-4">
            <p className="text-sm text-gray-600 text-center">
              Ingresá tu ID de Telegram para verificar tu cuenta
            </p>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                ID de Telegram
              </label>
              <input
                type="text"
                required
                value={telegramId}
                onChange={e => setTelegramId(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-green-500"
                placeholder="Ej: 8697104390"
              />
              <p className="text-xs text-gray-400 mt-1">
                Tu ID lo encontrás en el bot con el comando /id
              </p>
            </div>

            {error && <p className="text-red-600 text-sm text-center">{error}</p>}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-green-600 hover:bg-green-700 text-white font-semibold py-2 rounded-lg transition disabled:opacity-60"
            >
              {loading ? 'Verificando...' : 'Continuar'}
            </button>
          </form>
        )}

        {paso === 2 && perfil && (
          <form onSubmit={handleRegistrar} className="space-y-4">
            <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-center">
              <p className="text-sm font-medium text-green-800">✓ {perfil.nombre}</p>
              <p className="text-xs text-green-600 capitalize">{perfil.tipo}</p>
            </div>

            <p className="text-sm text-gray-600 text-center">
              Elegí el email y contraseña para tu cuenta
            </p>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
              <input
                type="email"
                required
                value={email}
                onChange={e => setEmail(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-green-500"
                placeholder="tu@email.com"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Contraseña</label>
              <input
                type="password"
                required
                value={password}
                onChange={e => setPassword(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-green-500"
                placeholder="Mínimo 8 caracteres"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Repetir contraseña</label>
              <input
                type="password"
                required
                value={confirm}
                onChange={e => setConfirm(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-green-500"
                placeholder="••••••••"
              />
            </div>

            {error && <p className="text-red-600 text-sm text-center">{error}</p>}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-green-600 hover:bg-green-700 text-white font-semibold py-2 rounded-lg transition disabled:opacity-60"
            >
              {loading ? 'Creando cuenta...' : 'Crear cuenta'}
            </button>

            <button
              type="button"
              onClick={() => { setPaso(1); setError('') }}
              className="w-full text-sm text-gray-500 hover:text-gray-700"
            >
              ← Volver
            </button>
          </form>
        )}

        <p className="text-center text-sm text-gray-500 mt-6">
          ¿Ya tenés cuenta?{' '}
          <Link href="/login" className="text-green-600 hover:underline font-medium">
            Iniciá sesión
          </Link>
        </p>
      </div>
    </div>
  )
}
