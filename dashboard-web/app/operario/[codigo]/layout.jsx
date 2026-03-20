import { createAdminClient } from '../../../lib/supabase-admin'
import { notFound } from 'next/navigation'
import PortalNav from '../../../components/PortalNav'

export default async function OperarioLayout({ children, params }) {
  const { codigo } = await params
  const supabase = createAdminClient()

  const { data: operario } = await supabase
    .from('usuarios')
    .select('id, nombre')
    .eq('codigo_acceso', codigo)
    .single()

  if (!operario) notFound()

  return (
    <div className="flex min-h-screen">
      <PortalNav
        role="operario"
        nombre={operario.nombre}
        basePath={`/operario/${codigo}`}
      />
      <main className="flex-1 p-4 md:p-6 pt-16 md:pt-6 overflow-auto bg-gray-100">
        {children}
      </main>
    </div>
  )
}
