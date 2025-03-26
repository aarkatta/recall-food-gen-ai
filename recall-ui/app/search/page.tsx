'use client'

import { useState, useEffect, Suspense } from 'react'
import { useSearchParams } from 'next/navigation'
import Main from '../Main'

function SearchResults() {
  const [recalls, setRecalls] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const searchParams = useSearchParams()
  const query = searchParams.get('query')

  useEffect(() => {
    if (!query) {
      setRecalls([])
      setLoading(false)
      return
    }

    const fetchRecalls = async () => {
      try {
        const functionHost =
          process.env.NEXT_PUBLIC_AZURE_FUNCTION_HOST || 'foodalert.azurewebsites.net'
        const function_key = process.env.NEXT_PUBLIC_AZ_FUNC_KEY_SEARCH_RECALLS
        const url = `https://${functionHost}/api/search?q=${query}&code=${function_key}`
        const response = await fetch(url)
        if (!response.ok) {
          throw new Error(`Error fetching search results: ${response.status}`)
        }

        const data = await response.json()
        setRecalls(data || [])
      } catch (err) {
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }

    fetchRecalls()
  }, [query])

  if (loading) return <p>Loading search results...</p>
  if (error) return <p className="text-red-500">Error: {error}</p>

  return <Main recalls={recalls} showAll={true} />
}

export default function SearchResultsPage() {
  return (
    <Suspense fallback={<p>Loading search results...</p>}>
      <SearchResults />
    </Suspense>
  )
}
