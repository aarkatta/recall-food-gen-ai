import SectionContainer from '@/components/SectionContainer'
import PageTitle from '@/components/PageTitle'
import Link from 'next/link'

export default function RecallLayout({ recall }) {
  return (
    <SectionContainer>
      <article>
        <div className="prose dark:prose-invert max-w-none pt-10 pb-8">
          <div className="mt-10">
            <Link
              href="/"
              className="text-primary-500 hover:text-primary-600 dark:hover:text-primary-400 font-bold"
            >
              ← Back to Recent Recalls
            </Link>
          </div>
          {recall.summary.split('\n\n').map((section, index) => {
            if (!section.trim()) return null
            const [title, ...content] = section.split('\n')
            const filteredContent = content.filter(
              (line) => line.trim() !== '' && !/^\s*-\s*$/.test(line)
            )
            if (filteredContent.length === 0) return null

            return (
              <div key={index} className="mb-6 border-b pb-4">
                <h2 className="mt-4 text-xl font-bold">
                  {title.replace('**', '').replace('**', '').replace(':', '').trim()}
                </h2>
                {filteredContent.map((line, i) => {
                  const formattedLine = line.replace(/- \*\*|\*\*/g, '').trim()
                  const urlMatch = formattedLine.match(/\[(.*?)\]\((.*?)\)/)

                  if (urlMatch) {
                    return (
                      <p key={i} className="mt-2">
                        {formattedLine.replace(urlMatch[0], '')}
                        <Link
                          href={urlMatch[2]}
                          className="text-primary-500 hover:text-primary-600 dark:hover:text-primary-400"
                        >
                          {urlMatch[1]}
                        </Link>
                      </p>
                    )
                  }
                  return (
                    <p key={i} className="mt-2">
                      {formattedLine}
                    </p>
                  )
                })}
              </div>
            )
          })}
        </div>
      </article>
    </SectionContainer>
  )
}
