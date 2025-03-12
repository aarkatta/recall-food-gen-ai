'use client'

import { useState, useEffect } from 'react'
import { useRouter, usePathname } from 'next/navigation'

const SearchButton = () => {
  const [query, setQuery] = useState('')
  const router = useRouter()
  const pathname = usePathname()

  useEffect(() => {
    // Clear search input when navigating to the home page
    if (pathname === '/') {
      setQuery('')
    }
  }, [pathname])

  const handleSearch = (e) => {
    e.preventDefault()
    if (!query.trim()) return // Prevent empty search submission

    // Navigate to search results page with query
    router.push(`/search?query=${encodeURIComponent(query)}`)
  }

  return (
    <div className="relative flex items-center space-x-4">
      {/* Search Input */}
      <form onSubmit={handleSearch} className="relative w-full">
        <input
          type="text"
          placeholder="Search recalls..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="focus:ring-primary-500 w-full rounded-full border bg-white py-2 pr-4 pl-10 text-gray-900 placeholder-gray-500 focus:ring-2 focus:outline-none dark:bg-gray-900 dark:text-gray-100 dark:placeholder-gray-400"
        />
        {/* Search Icon */}
        <button
          type="submit"
          className="absolute top-1/2 left-3 -translate-y-1/2 text-gray-500 dark:text-gray-400"
          aria-label="Search"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={1.5}
            stroke="currentColor"
            className="h-5 w-5"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"
            />
          </svg>
        </button>
      </form>

      {/* Theme Toggle Button (Placeholder) */}
      <button
        className="hover:text-primary-500 dark:hover:text-primary-400 text-gray-900 dark:text-gray-100"
        aria-label="Toggle Theme"
      ></button>
    </div>
  )
}

export default SearchButton
