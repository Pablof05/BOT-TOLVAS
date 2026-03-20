import { redirect } from 'next/navigation'

export default async function ContratistaPortalPage({ params }) {
  const { codigo } = await params
  redirect(`/contratista/${codigo}/camiones`)
}
