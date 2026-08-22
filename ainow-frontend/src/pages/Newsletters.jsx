import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { getNewsletters } from "../services/api"

function Newsletters() {
  const [newsletters, setNewsletters] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  useEffect(() => {
    async function loadNewsletters() {
      try {
        const data = await getNewsletters()
        setNewsletters(data)
      } catch (error) {
        setError(error.message)
      } finally {
        setLoading(false)
      }
    }

    loadNewsletters()
  }, [])

  return (
    <main className="min-h-screen bg-black px-6 py-24 text-white">
      <div className="mx-auto max-w-7xl">

        <div className="max-w-3xl">
          <p className="text-sm font-semibold uppercase tracking-widest text-gray-500">
            Newsletter Archive
          </p>

          <h1 className="mt-4 text-5xl font-bold md:text-6xl">
            Previous Editions
          </h1>

          <p className="mt-6 text-lg leading-8 text-gray-400">
            Explore previous editions of AINow and catch up on the latest
            developments in artificial intelligence.
          </p>
        </div>

        {loading && (
          <p className="mt-16 text-gray-500">
            Loading newsletters...
          </p>
        )}

        {error && (
          <p className="mt-16 text-red-400">
            {error}
          </p>
        )}

        {!loading && !error && newsletters.length === 0 && (
          <p className="mt-16 text-gray-500">
            No newsletters have been published yet.
          </p>
        )}

        {!loading && !error && newsletters.length > 0 && (
          <div className="mt-16 grid gap-6 md:grid-cols-2">
            {newsletters.map((newsletter) => (
              <article
                key={newsletter.id}
                className="group rounded-2xl border border-gray-800 p-8 transition hover:border-gray-600"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-500">
                    {new Date(newsletter.published_at).toLocaleDateString(
                      "en-US",
                      {
                        year: "numeric",
                        month: "long",
                        day: "numeric",
                      }
                    )}
                  </span>

                  <span className="rounded-full border border-gray-800 px-3 py-1 text-xs text-gray-400">
                    AI
                  </span>
                </div>

                <h2 className="mt-8 text-2xl font-bold transition group-hover:text-gray-300">
                  {newsletter.title}
                </h2>

                <Link
                  to={`/newsletters/${newsletter.id}`}
                  className="mt-8 inline-block font-medium text-white"
                >
                  Read Newsletter →
                </Link>
              </article>
            ))}
          </div>
        )}

      </div>
    </main>
  )
}

export default Newsletters