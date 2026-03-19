import './globals.css'

export const metadata = {
  title: 'Tolvas – Dashboard',
  description: 'Panel de control para contratistas',
}

export default function RootLayout({ children }) {
  return (
    <html lang="es">
      <body className="bg-gray-100 text-gray-900 min-h-screen">
        {children}
      </body>
    </html>
  )
}
