export default function NotFound() {
  return (
    <div className="min-h-screen bg-gray-100 flex items-center justify-center">
      <div className="bg-white rounded-2xl shadow p-10 max-w-md text-center">
        <p className="text-5xl mb-4">🔒</p>
        <h1 className="text-xl font-bold text-gray-800 mb-2">Acceso no válido</h1>
        <p className="text-gray-500 text-sm">
          El código no existe o no tenés permisos para acceder a este panel.
        </p>
        <p className="text-gray-400 text-xs mt-4">
          Pedile el link correcto a tu contratista.
        </p>
      </div>
    </div>
  )
}
