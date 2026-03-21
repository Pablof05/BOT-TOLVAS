'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { createClient } from '../lib/supabase'

export default function AutoRefresh() {
  const router = useRouter()

  useEffect(() => {
    const supabase = createClient()
    const channel = supabase
      .channel('activos-realtime')
      .on('postgres_changes', { event: '*', schema: 'public', table: 'descargas' }, () => router.refresh())
      .on('postgres_changes', { event: '*', schema: 'public', table: 'camiones' }, () => router.refresh())
      .subscribe()

    return () => { supabase.removeChannel(channel) }
  }, [router])

  return null
}
