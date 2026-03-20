import { createAdminClient } from '../../../../lib/supabase-admin'
import { notFound } from 'next/navigation'
import CamionesContent from '../../../../components/CamionesContent'

export default async function Page({ params, searchParams }) {
  const { codigo } = await params
  const supabase = createAdminClient()

  const { data: cliente } = await supabase
    .from('clientes')
    .select('id')
    .eq('codigo_acceso', codigo)
    .single()

  if (!cliente) notFound()

  return (
    <CamionesContent
      basePath={`/cliente/${codigo}/camiones`}
      searchParams={searchParams}
      fixedClienteId={cliente.id}
    />
  )
}
