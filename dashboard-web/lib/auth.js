import { createClient } from './supabase-server'

/**
 * Devuelve { user, role: 'contratista'|'cliente', profile }
 * Si no hay usuario autenticado devuelve null
 */
export async function getUserProfile() {
  const supabase = createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) return null

  // Intentar como contratista primero
  const { data: contratista } = await supabase
    .from('contratistas')
    .select('id, nombre, apellido')
    .eq('user_id', user.id)
    .single()

  if (contratista) {
    return { user, role: 'contratista', profile: contratista }
  }

  // Si no, intentar como cliente
  const { data: cliente } = await supabase
    .from('clientes')
    .select('id, nombre, apellido, contratista_id')
    .eq('user_id', user.id)
    .single()

  if (cliente) {
    return { user, role: 'cliente', profile: cliente }
  }

  return { user, role: null, profile: null }
}
