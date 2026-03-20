'use server'

import { createAdminClient } from '../lib/supabase-admin'
import { revalidatePath } from 'next/cache'
import crypto from 'crypto'

export async function generarCodigoOperario(id) {
  const supabase = createAdminClient()
  const codigo   = crypto.randomBytes(12).toString('hex')
  await supabase.from('usuarios').update({ codigo_acceso: codigo }).eq('id', id)
  revalidatePath('/dashboard/usuarios')
}

export async function generarCodigoCliente(id) {
  const supabase = createAdminClient()
  const codigo   = crypto.randomBytes(12).toString('hex')
  await supabase.from('clientes').update({ codigo_acceso: codigo }).eq('id', id)
  revalidatePath('/dashboard/usuarios')
}
