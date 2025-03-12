import Main from './Main'

export default async function RecallsPage() {
  try {
    const functionHost =
      process.env.NEXT_PUBLIC_AZURE_FUNCTION_HOST || 'foodalert.azurewebsites.net'
    const functionKey = process.env.AZ_FUNC_KEY_RECENT_RECALLS
    const url = `https://${functionHost}/api/recent_recalls?code=${functionKey}`

    // Add a timeout to the fetch request
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 5000) // 5 second timeout

    const response = await fetch(url, {
      signal: controller.signal,
    })

    clearTimeout(timeoutId)

    if (!response.ok) {
      console.error(`Error fetching recalls: ${response.status}`)
      return <Main recalls={[]} showAll={true} />
    }

    const responseText = await response.text()

    // Check if the response is empty
    if (!responseText.trim()) {
      console.error('Empty response received from API')
      return <Main recalls={[]} showAll={true} />
    }

    // Try parsing the JSON
    const data = JSON.parse(responseText)
    const recalls = data.recalls || []

    return <Main recalls={recalls} showAll={true} />
  } catch (error) {
    console.error('Error rendering recalls page:', error)
    // Return the component with empty recalls array
    return <Main recalls={[]} showAll={true} />
  }
}
