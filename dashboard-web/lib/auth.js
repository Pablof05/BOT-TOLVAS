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

  // Intentar como cliente via tabla cliente_usuarios (soporte multi-empleado)
  const { data: clienteUsuario } = await supabase
    .from('cliente_usuarios')
    .select('cliente_id')
    .eq('user_id', user.id)
    .single()

  if (clienteUsuario) {
    const { data: cliente } = await supabase
      .from('clientes')
      .select('id, nombre, apellido, contratista_id')
      .eq('id', clienteUsuario.cliente_id)
      .single()

    if (cliente) {
      return { user, role: 'cliente', profile: cliente }
    }
  }

  // Fallback: user_id directo en clientes (cuentas previas)
  const { data: clienteLegacy } = await supabase
    .from('clientes')
    .select('id, nombre, apellido, contratista_id')
    .eq('user_id', user.id)
    .single()

  if (clienteLegacy) {
    return { user, role: 'cliente', profile: clienteLegacy }
  }

  // Intentar como operario
  const { data: operario } = await supabase
    .from('usuarios')
    .select('id, nombre, contratista_id')
    .eq('user_id', user.id)
    .eq('rol', 'operario')
    .single()

  if (operario) {
    return { user, role: 'operario', profile: operario }
  }

  return { user, role: null, profile: null }
}
