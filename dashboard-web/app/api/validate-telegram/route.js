import { createClient } from '@supabase/supabase-js'
import { NextResponse } from 'next/server'

const supabaseAdmin = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL,
  process.env.SUPABASE_SERVICE_ROLE_KEY
)

export async function POST(request) {
  const { telegram_id } = await request.json()

  if (!telegram_id?.trim()) {
    return NextResponse.json({ error: 'Ingresá tu ID de Telegram' }, { status: 400 })
  }

  const tid = telegram_id.trim()

  // Buscar contratista
  const { data: contratista } = await supabaseAdmin
    .from('contratistas')
    .select('id, nombre, apellido, user_id')
    .eq('telegram_id', tid)
    .single()

  if (contratista) {
    if (contratista.user_id) {
      return NextResponse.json({ error: 'Este ID ya tiene una cuenta registrada. Usá el login.' }, { status: 409 })
    }
    return NextResponse.json({
      tipo: 'contratista',
      ref_id: contratista.id,
      nombre: `${contratista.nombre} ${contratista.apellido}`,
    })
  }

  // Buscar cliente
  const { data: cliente } = await supabaseAdmin
    .from('clientes')
    .select('id, nombre, apellido')
    .eq('telegram_id', tid)
    .single()

  if (cliente) {
    return NextResponse.json({
      tipo: 'cliente',
      ref_id: cliente.id,
      nombre: `${cliente.nombre} ${cliente.apellido}`,
    })
  }

  // Buscar operario
  const { data: operario } = await supabaseAdmin
    .from('usuarios')
    .select('id, nombre, user_id')
    .eq('telegram_id', tid)
    .eq('rol', 'operario')
    .single()

  if (operario) {
    if (operario.user_id) {
      return NextResponse.json({ error: 'Este ID ya tiene una cuenta registrada. Usá el login.' }, { status: 409 })
    }
    return NextResponse.json({
      tipo: 'operario',
      ref_id: operario.id,
      nombre: operario.nombre,
    })
  }

  return NextResponse.json({ error: 'No encontramos ninguna cuenta con ese ID de Telegram.' }, { status: 404 })
}
