import SilobolsasContent from '../../../components/SilobolsasContent'

export default async function SilobolsasPage({ searchParams }) {
  return <SilobolsasContent basePath="/dashboard/silobolsas" searchParams={searchParams} />
}
