import SilobolsasContent from '../../../../components/SilobolsasContent'

export default async function Page({ params, searchParams }) {
  const { codigo } = await params
  return <SilobolsasContent basePath={`/operario/${codigo}/silobolsas`} searchParams={searchParams} />
}
