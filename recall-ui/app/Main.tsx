import Link from 'next/link'
import siteMetadata from '@/data/siteMetadata'
import { formatDate } from 'pliny/utils/formatDate'

const MAX_DISPLAY = 10

export default function Main({ recalls, showAll = false }) {
  const displayedRecalls = showAll ? recalls : recalls.slice(0, MAX_DISPLAY)

  return (
    <>
      <div className="divide-y divide-gray-200 dark:divide-gray-700">
        <div className="space-y-2 pt-6 pb-8 md:space-y-5">
          <h1 className="text-3xl leading-9 font-extrabold tracking-tight text-gray-900 sm:text-4xl sm:leading-10 md:text-6xl md:leading-14 dark:text-gray-100">
            Latest Recalls
          </h1>
          <p className="text-lg leading-7 text-gray-500 dark:text-gray-400">
            Stay informed about the latest food recalls across the country.
          </p>
        </div>
        <ul className="divide-y divide-gray-200 dark:divide-gray-700">
          {!recalls.length && 'No recalls found.'}
          {displayedRecalls.map((recall) => {
            const {
              recall_number,
              report_date,
              product_description,
              classification,
              reason_for_recall,
            } = recall
            return (
              <li key={recall_number} className="py-12">
                <article>
                  <div className="space-y-2 xl:grid xl:grid-cols-4 xl:items-baseline xl:space-y-0">
                    <dl>
                      <div className="prose max-w-none text-gray-500 dark:text-gray-400">
                        <h4 className="font-semibold">Report Date</h4>
                      </div>
                      <dd className="text-base leading-6 font-medium text-gray-500 dark:text-gray-400">
                        <time dateTime={report_date}>
                          {formatDate(report_date, siteMetadata.locale)}
                        </time>
                      </dd>
                    </dl>
                    <div className="space-y-5 xl:col-span-3">
                      <div className="space-y-6">
                        <div>
                          <h2 className="text-2xl leading-8 font-bold tracking-tight">
                            <Link
                              href={`/recalls/${recall_number}`}
                              className="text-gray-900 hover:underline dark:text-gray-100"
                            >
                              {reason_for_recall}
                            </Link>
                          </h2>
                          <p className="text-sm text-gray-500 dark:text-gray-400">
                            {classification}
                          </p>
                        </div>
                        <div className="prose max-w-none text-gray-500 dark:text-gray-400">
                          {product_description}
                        </div>
                      </div>
                      <div className="text-base leading-6 font-medium">
                        <Link
                          href={`/recalls/${recall_number}`}
                          className="text-primary-500 hover:text-primary-600 dark:hover:text-primary-400"
                          aria-label={`Read more: "${product_description}"`}
                        >
                          Read more &rarr;
                        </Link>
                      </div>
                    </div>
                  </div>
                </article>
              </li>
            )
          })}
        </ul>
      </div>
      {!showAll && recalls.length > MAX_DISPLAY && (
        <div className="flex justify-end text-base leading-6 font-medium">
          <Link
            href="/recalls"
            className="text-primary-500 hover:text-primary-600 dark:hover:text-primary-400"
            aria-label="All recalls"
          >
            All Recalls &rarr;
          </Link>
        </div>
      )}
    </>
  )
}
