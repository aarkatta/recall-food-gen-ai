import { notFound } from 'next/navigation'
import RecallLayout from '@/layouts/RecallLayout'

interface PageProps {
  params: Promise<{ id: string }>
}
export default async function RecallPage({ params }: PageProps) {
  const resolvedParams = await params
  const { id } = resolvedParams
  if (!id) {
    return <div className="text-center text-red-500">Invalid Recall ID</div>
  }
  try {
    const functionHost =
      process.env.NEXT_PUBLIC_AZURE_FUNCTION_HOST || 'foodalert.azurewebsites.net'
    const functionKey = process.env.AZ_FUNC_KEY_GET_RECALL_BY_ID
    const url = `https://${functionHost}/api/recall/${id}?code=${functionKey}`
    const response = await fetch(url)

    if (!response.ok) {
      throw new Error(`Failed to fetch recall details: ${response.status}`)
    }
    const recall = await response.json()
    return <RecallLayout recall={recall} />
  } catch (error) {
    console.error('Error fetching recall details:', error)
    return <div className="text-center text-red-500">Error loading recall details.</div>
  }
}
