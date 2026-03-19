import Sidebar from '../../components/Sidebar'
import { getUserProfile } from '../../lib/auth'
import { redirect } from 'next/navigation'

export default async function DashboardLayout({ children }) {
  const userProfile = await getUserProfile()

  if (!userProfile) redirect('/login')

  return (
    <div className="flex min-h-screen">
      <Sidebar role={userProfile.role} profile={userProfile.profile} />
      <main className="flex-1 p-6 overflow-auto bg-gray-100">
        {children}
      </main>
    </div>
  )
}
