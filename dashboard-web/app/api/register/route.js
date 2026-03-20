import { createClient } from '@supabase/supabase-js'
import { NextResponse } from 'next/server'

const supabaseAdmin = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL,
  process.env.SUPABASE_SERVICE_ROLE_KEY
)

export async function POST(request) {
  const { telegram_id, tipo, ref_id, email, password } = await request.json()

  if (!telegram_id || !tipo || !ref_id || !email || !password) {
    return NextResponse.json({ error: 'Faltan datos' }, { status: 400 })
  }

  if (password.length < 8) {
    return NextResponse.json({ error: 'La contraseña debe tener al menos 8 caracteres' }, { status: 400 })
  }

  // Crear usuario en Supabase Auth
  const { data: authData, error: authError } = await supabaseAdmin.auth.admin.createUser({
    email,
    password,
    email_confirm: true,
  })

  if (authError) {
    if (authError.message?.includes('already registered')) {
      return NextResponse.json({ error: 'Ese email ya está registrado' }, { status: 409 })
    }
    return NextResponse.json({ error: 'Error al crear la cuenta. Intentá con otro email.' }, { status: 500 })
  }

  const user_id = authData.user.id

  if (tipo === 'contratista') {
    const { error } = await supabaseAdmin
      .from('contratistas')
      .update({ user_id })
      .eq('id', ref_id)

    if (error) {
      await supabaseAdmin.auth.admin.deleteUser(user_id)
      return NextResponse.json({ error: 'Error al vincular la cuenta' }, { status: 500 })
    }
  } else if (tipo === 'cliente') {
    const { error } = await supabaseAdmin
      .from('cliente_usuarios')
      .insert({ user_id, cliente_id: ref_id, telegram_id })

    if (error) {
      await supabaseAdmin.auth.admin.deleteUser(user_id)
      return NextResponse.json({ error: 'Error al vincular la cuenta' }, { status: 500 })
    }
  }

  return NextResponse.json({ ok: true })
}
