import { createAdminClient } from '../../../../lib/supabase-admin'
import { notFound } from 'next/navigation'
import CopiarLink from '../../../../components/CopiarLink'
import { generarCodigoOperario, generarCodigoCliente } from '../../../actions'

function TagVinculado({ telegramId }) {
  return telegramId
    ? <span className="px-2 py-0.5 text-xs rounded-full bg-blue-100 text-blue-700">Vinculado ✓</span>
    : <span className="px-2 py-0.5 text-xs rounded-full bg-yellow-100 text-yellow-700">Sin vincular</span>
}

export default async function UsuariosPage({ params, searchParams }) {
  const { codigo } = await params
  const supabase = createAdminClient()
  const tab = searchParams?.tab || 'operarios'

  const { data: contratista } = await supabase
    .from('contratistas')
    .select('id')
    .eq('codigo_acceso', codigo)
    .single()

  if (!contratista) notFound()

  const [{ data: operarios, error: errOp }, { data: clientes, error: errCl }] = await Promise.all([
    supabase.from('usuarios').select('id, nombre, telegram_id, activo, codigo_acceso').eq('contratista_id', contratista.id).order('nombre'),
    supabase.from('clientes').select('id, nombre, apellido, telegram_id, codigo_acceso').eq('contratista_id', contratista.id).order('nombre'),
  ])

  if (errOp || errCl) {
    return (
      <div className="p-6 bg-red-50 rounded-xl text-red-700">
        <p className="font-semibold">Error al cargar usuarios</p>
      </div>
    )
  }

  const isOperarios = tab === 'operarios'
  const baseUrl = process.env.NEXT_PUBLIC_APP_URL || ''
  const base = `/contratista/${codigo}/usuarios`

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-800 mb-6">Usuarios</h1>

      <div className="flex gap-2 mb-5">
        <a href={`${base}?tab=operarios`}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition ${isOperarios ? 'bg-green-600 text-white' : 'bg-white text-gray-600 border'}`}>
          Operarios ({operarios?.length ?? 0})
        </a>
        <a href={`${base}?tab=clientes`}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition ${!isOperarios ? 'bg-green-600 text-white' : 'bg-white text-gray-600 border'}`}>
          Clientes ({clientes?.length ?? 0})
        </a>
      </div>

      {isOperarios ? (
        <div className="bg-white rounded-2xl shadow overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 border-b text-xs uppercase tracking-wide">
                <th className="px-4 py-3">Nombre</th>
                <th className="px-4 py-3">Estado Telegram</th>
                <th className="px-4 py-3">Activo</th>
                <th className="px-4 py-3">Acceso al panel</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {!operarios?.length ? (
                <tr><td colSpan={4} className="text-center py-10 text-gray-400">No hay operarios</td></tr>
              ) : operarios.map(o => (
                <tr key={o.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium">{o.nombre}</td>
                  <td className="px-4 py-3"><TagVinculado telegramId={o.telegram_id} /></td>
                  <td className="px-4 py-3">{o.activo ? <span className="text-green-600 font-medium">Sí</span> : <span className="text-gray-400">No</span>}</td>
                  <td className="px-4 py-3 flex items-center gap-2">
                    {o.codigo_acceso
                      ? <CopiarLink url={`${baseUrl}/operario/${o.codigo_acceso}`} />
                      : <form action={generarCodigoOperario.bind(null, o.id)}>
                          <button type="submit" className="text-xs px-2 py-1 rounded bg-gray-100 text-gray-600 hover:bg-gray-200 transition">Generar link</button>
                        </form>
                    }
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="bg-white rounded-2xl shadow overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 border-b text-xs uppercase tracking-wide">
                <th className="px-4 py-3">Nombre</th>
                <th className="px-4 py-3">Estado Telegram</th>
                <th className="px-4 py-3">Acceso al panel</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {!clientes?.length ? (
                <tr><td colSpan={3} className="text-center py-10 text-gray-400">No hay clientes</td></tr>
              ) : clientes.map(c => (
                <tr key={c.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium">{c.nombre} {c.apellido}</td>
                  <td className="px-4 py-3"><TagVinculado telegramId={c.telegram_id} /></td>
                  <td className="px-4 py-3 flex items-center gap-2">
                    {c.codigo_acceso
                      ? <CopiarLink url={`${baseUrl}/cliente/${c.codigo_acceso}`} />
                      : <form action={generarCodigoCliente.bind(null, c.id)}>
                          <button type="submit" className="text-xs px-2 py-1 rounded bg-gray-100 text-gray-600 hover:bg-gray-200 transition">Generar link</button>
                        </form>
                    }
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
