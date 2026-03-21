import { createAdminClient } from '../../../lib/supabase-admin'
import { notFound } from 'next/navigation'
import Sidebar from '../../../components/Sidebar'
import AutoRefresh from '../../../components/AutoRefresh'

export default async function ContratistaPortalLayout({ children, params }) {
  const { codigo } = await params
  const supabase = createAdminClient()

  const { data: contratista } = await supabase
    .from('contratistas')
    .select('id, nombre, apellido')
    .eq('codigo_acceso', codigo)
    .single()

  if (!contratista) notFound()

  const profile = { nombre: contratista.nombre, apellido: contratista.apellido }

  return (
    <div className="flex min-h-screen">
      <Sidebar role="contratista" profile={profile} basePath={`/contratista/${codigo}`} />
      <main className="flex-1 p-4 md:p-6 pt-16 md:pt-6 overflow-auto bg-gray-100">
        <AutoRefresh />
        {children}
      </main>
    </div>
  )
}
