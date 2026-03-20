import { redirect } from 'next/navigation'

export default async function ClientePage({ params }) {
  const { codigo } = await params
  redirect(`/cliente/${codigo}/camiones`)
}
