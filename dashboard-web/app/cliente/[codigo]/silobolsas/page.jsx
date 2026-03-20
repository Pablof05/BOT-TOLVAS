import { createAdminClient } from '../../../../lib/supabase-admin'
import { notFound } from 'next/navigation'
import SilobolsasContent from '../../../../components/SilobolsasContent'

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
    <SilobolsasContent
      basePath={`/cliente/${codigo}/silobolsas`}
      searchParams={searchParams}
      fixedClienteId={cliente.id}
    />
  )
}
