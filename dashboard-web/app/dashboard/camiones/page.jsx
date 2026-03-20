import CamionesContent from '../../../components/CamionesContent'

export default async function CamionesPage({ searchParams }) {
  return <CamionesContent basePath="/dashboard/camiones" searchParams={searchParams} />
}
