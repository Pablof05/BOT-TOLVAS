import SilobolsasContent from '../../../../components/SilobolsasContent'

export default async function Page({ params, searchParams }) {
  const { codigo } = await params
  return <SilobolsasContent basePath={`/contratista/${codigo}/silobolsas`} searchParams={searchParams} />
}
