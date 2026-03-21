import { createClient } from '@supabase/supabase-js'
import { unstable_noStore as noStore } from 'next/cache'

export function createAdminClient() {
  noStore()
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY

  if (!url || !key) {
    throw new Error(
      `Faltan variables de entorno en Vercel: ${!url ? 'NEXT_PUBLIC_SUPABASE_URL ' : ''}${!key ? 'SUPABASE_SERVICE_ROLE_KEY' : ''}`
    )
  }

  return createClient(url, key)
}
