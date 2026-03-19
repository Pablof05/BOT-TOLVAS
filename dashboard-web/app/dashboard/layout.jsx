import Sidebar from '../../components/Sidebar'
import { createClient } from '../../lib/supabase-server'
import { redirect } from 'next/navigation'

export default async function DashboardLayout({ children }) {
  const supabase = createClient()
  const { data: { user } } = await supabase.auth.getUser()

  if (!user) redirect('/login')

  // Buscar datos del contratista vinculado a este usuario
  const { data: contratista } = await supabase
    .from('contratistas')
    .select('id, nombre, apellido')
    .eq('user_id', user.id)
    .single()

  return (
    <div className="flex min-h-screen">
      <Sidebar contratista={contratista} />
      <main className="flex-1 p-6 overflow-auto">
        {children}
      </main>
    </div>
  )
}
