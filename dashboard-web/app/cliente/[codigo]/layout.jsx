import { createAdminClient } from '../../../lib/supabase-admin'
import { notFound } from 'next/navigation'
import PortalNav from '../../../components/PortalNav'
import AutoRefresh from '../../../components/AutoRefresh'

export default async function ClienteLayout({ children, params }) {
  const { codigo } = await params
  const supabase = createAdminClient()

  const { data: cliente } = await supabase
    .from('clientes')
    .select('id, nombre, apellido')
    .eq('codigo_acceso', codigo)
    .single()

  if (!cliente) notFound()

  return (
    <div className="flex min-h-screen">
      <PortalNav
        role="cliente"
        nombre={cliente.nombre}
        apellido={cliente.apellido}
        basePath={`/cliente/${codigo}`}
      />
      <main className="flex-1 p-4 md:p-6 pt-16 md:pt-6 overflow-auto bg-gray-100">
        <AutoRefresh />
        {children}
      </main>
    </div>
  )
}
