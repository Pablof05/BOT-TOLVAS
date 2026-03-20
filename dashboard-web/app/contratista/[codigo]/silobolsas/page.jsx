import { createAdminClient } from '../../../../lib/supabase-admin'
import { notFound } from 'next/navigation'
import SilobolsasContent from '../../../../components/SilobolsasContent'

export default async function Page({ params, searchParams }) {
  const { codigo } = await params
  const supabase = createAdminClient()

  const { data: contratista } = await supabase
    .from('contratistas')
    .select('id')
    .eq('codigo_acceso', codigo)
    .single()

  if (!contratista) notFound()

  const { data: clientes } = await supabase
    .from('clientes')
    .select('id')
    .eq('contratista_id', contratista.id)

  const clienteIds = (clientes ?? []).map(c => c.id)

  return (
    <SilobolsasContent
      basePath={`/contratista/${codigo}/silobolsas`}
      searchParams={searchParams}
      allowedClienteIds={clienteIds}
    />
  )
}
