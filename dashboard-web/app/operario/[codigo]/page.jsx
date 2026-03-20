import { redirect } from 'next/navigation'

export default async function OperarioPage({ params }) {
  const { codigo } = await params
  redirect(`/operario/${codigo}/camiones`)
}
