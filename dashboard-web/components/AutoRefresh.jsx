'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { createClient } from '../lib/supabase'

export default function AutoRefresh() {
  const router = useRouter()
  const [status, setStatus] = useState('connecting')
  const [lastUpdate, setLastUpdate] = useState(null)

  useEffect(() => {
    const supabase = createClient()
    const channel = supabase
      .channel('activos-realtime')
      .on('postgres_changes', { event: '*', schema: 'public', table: 'descargas' }, () => {
        console.log('[AutoRefresh] cambio en descargas')
        setLastUpdate(new Date().toLocaleTimeString('es-AR'))
        router.refresh()
      })
      .on('postgres_changes', { event: '*', schema: 'public', table: 'camiones' }, () => {
        console.log('[AutoRefresh] cambio en camiones')
        setLastUpdate(new Date().toLocaleTimeString('es-AR'))
        router.refresh()
      })
      .subscribe((s) => {
        console.log('[AutoRefresh] estado suscripción:', s)
        setStatus(s)
      })

    return () => { supabase.removeChannel(channel) }
  }, [router])

  const dot = status === 'SUBSCRIBED'
    ? 'bg-green-400'
    : status === 'CHANNEL_ERROR' || status === 'TIMED_OUT'
    ? 'bg-red-400'
    : 'bg-yellow-400'

  return (
    <div className="flex items-center gap-1.5 text-xs text-gray-400 mb-2">
      <span className={`w-2 h-2 rounded-full ${dot} animate-pulse`} />
      {status === 'SUBSCRIBED'
        ? lastUpdate ? `Actualizado ${lastUpdate}` : 'Escuchando cambios...'
        : status === 'CHANNEL_ERROR' ? 'Error de conexión real-time'
        : status === 'TIMED_OUT' ? 'Conexión cortada'
        : 'Conectando...'}
    </div>
  )
}
