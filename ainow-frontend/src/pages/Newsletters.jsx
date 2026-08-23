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
      } catch (err) {
        setError(
          err.message ||
          "Unable to load newsletters."
        )
      } finally {
        setLoading(false)
      }
    }

    loadNewsletters()
  }, [])

  if (loading) {
    return (
      <main className="min-h-screen bg-black px-6 py-24 text-white">
        <div className="mx-auto max-w-7xl">
          <p className="text-gray-400">
            Loading newsletters...
          </p>
        </div>
      </main>
    )
  }

  if (error) {
    return (
      <main className="min-h-screen bg-black px-6 py-24 text-white">
        <div className="mx-auto max-w-7xl">
          <p className="text-red-400">
            {error}
          </p>
        </div>
      </main>
    )
  }

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
            Explore previous editions of AINow
            and catch up on the latest developments
            in artificial intelligence.
          </p>
        </div>

        {newsletters.length === 0 ? (
          <div className="mt-16 rounded-2xl border border-gray-800 p-8">
            <p className="text-gray-400">
              No published newsletters yet.
            </p>
          </div>
        ) : (
          <div className="mt-16 grid gap-6 md:grid-cols-2">

            {newsletters.map((newsletter) => (
              <article
                key={newsletter.id}
                className="group rounded-2xl border border-gray-800 p-8 transition hover:border-gray-600"
              >

                <div className="flex items-center justify-between gap-4">
                  <span className="text-sm text-gray-500">
                    {newsletter.published_at
                      ? new Date(
                          newsletter.published_at
                        ).toLocaleDateString(
                          "en-US",
                          {
                            year: "numeric",
                            month: "long",
                            day: "numeric",
                          }
                        )
                      : "Unpublished"}
                  </span>

                  <span className="rounded-full border border-gray-800 px-3 py-1 text-xs text-gray-400">
                    AINow
                  </span>
                </div>

                <h2 className="mt-8 text-2xl font-bold transition group-hover:text-gray-300">
                  {newsletter.title}
                </h2>

                <p className="mt-4 leading-7 text-gray-400">
                  A curated edition of the latest
                  AI news, research, trends and tools.
                </p>

                <Link
                  to={`/newsletters/${newsletter.id}`}
                  className="mt-8 inline-block font-medium text-white hover:text-gray-300"
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