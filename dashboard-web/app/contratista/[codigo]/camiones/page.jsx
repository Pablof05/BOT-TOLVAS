import CamionesContent from '../../../../components/CamionesContent'

export default async function Page({ params, searchParams }) {
  const { codigo } = await params
  return <CamionesContent basePath={`/contratista/${codigo}/camiones`} searchParams={searchParams} />
}
