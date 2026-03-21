import Sidebar from '../../components/Sidebar'
import AutoRefresh from '../../components/AutoRefresh'

export default function DashboardLayout({ children }) {
  return (
    <div className="flex min-h-screen">
      <Sidebar role="contratista" profile={null} />
      <main className="flex-1 p-4 md:p-6 pt-16 md:pt-6 overflow-auto bg-gray-100">
        <AutoRefresh />
        {children}
      </main>
    </div>
  )
}
