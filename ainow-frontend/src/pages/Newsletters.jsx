import { useEffect, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { getNewsletters, searchNewsletters } from "../services/api"

const SECTION_LABELS = {
  quick_news: "Quick News",
  research_spotlight: "Research",
  paper_of_week: "Paper of the Week",
  deep_dive: "Deep Dive",
  resources: "Resource",
}

function formatDate(value) {
  if (!value) return "Unpublished"

  return new Date(value).toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  })
}

function SearchResults({ query, search }) {
  if (search.query !== query) {
    return <p className="mt-10 text-gray-500">Searching…</p>
  }

  if (search.error) {
    return <p className="mt-10 text-red-400">{search.error}</p>
  }

  if (search.results.length === 0) {
    return (
      <div className="mt-10 rounded-2xl border border-gray-800 p-8">
        <p className="text-gray-400">No past issues cover “{query}” yet.</p>
      </div>
    )
  }

  return (
    <div className="mt-10 flex flex-col gap-4">
      <p className="text-sm text-gray-500">
        {search.results.length === 1 ? "1 issue mentions" : `${search.results.length} issues mention`} “{query}”
      </p>

      {search.results.map((issue) => (
        <Link
          key={issue.id}
          to={`/newsletters/${issue.id}`}
          className="group flex flex-col gap-5 rounded-2xl border border-gray-800 p-6 transition hover:border-gray-600 sm:flex-row"
        >
          {issue.cover_image && (
            <img
              src={issue.cover_image}
              alt=""
              loading="lazy"
              referrerPolicy="no-referrer"
              onError={(event) => {
                event.currentTarget.style.display = "none"
              }}
              className="aspect-[2/1] w-full shrink-0 rounded-xl bg-neutral-900 object-cover sm:w-48"
            />
          )}

          <div className="min-w-0">
            <p className="text-sm text-gray-500">{formatDate(issue.published_at)}</p>
            <h2 className="mt-1 text-xl font-bold group-hover:text-gray-300">{issue.headline || issue.title}</h2>

            <ul className="mt-4 flex flex-col gap-3">
              {issue.matches.map((match) => (
                <li key={match.headline} className="text-sm">
                  <span className="mr-2 rounded-full border border-gray-800 px-2 py-0.5 text-xs text-gray-400">
                    {SECTION_LABELS[match.section] || match.section.replaceAll("_", " ")}
                  </span>
                  <span className="font-medium text-gray-200">{match.headline}</span>
                  {match.summary && <p className="mt-1 line-clamp-2 text-gray-500">{match.summary}</p>}
                </li>
              ))}
            </ul>
          </div>
        </Link>
      ))}
    </div>
  )
}

function Newsletters() {
  const [newsletters, setNewsletters] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  // The query lives in the URL so a search can be shared.
  const [searchParams, setSearchParams] = useSearchParams()
  const query = searchParams.get("q") || ""
  const trimmed = query.trim()
  const searching = trimmed.length >= 2
  const [search, setSearch] = useState({ query: "", results: [], error: "" })

  useEffect(() => {
    if (!searching) return undefined

    const controller = new AbortController()

    const timer = setTimeout(() => {
      searchNewsletters(trimmed, { signal: controller.signal })
        .then((results) => setSearch({ query: trimmed, results, error: "" }))
        .catch((err) => {
          if (err.name !== "AbortError") {
            setSearch({ query: trimmed, results: [], error: err.message })
          }
        })
    }, 300)

    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [searching, trimmed])

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

        <div className="mt-10 max-w-2xl">
          <label htmlFor="archive-search" className="sr-only">
            Search past issues
          </label>
          <input
            id="archive-search"
            type="search"
            value={query}
            onChange={(event) =>
              setSearchParams(event.target.value ? { q: event.target.value } : {}, { replace: true })
            }
            placeholder="Search past issues: a model, company or topic…"
            className="w-full rounded-xl border border-gray-800 bg-neutral-950 px-5 py-3.5 text-white placeholder:text-gray-600 focus:border-gray-500 focus:outline-none"
          />
        </div>

        {searching ? (
          <SearchResults query={trimmed} search={search} />
        ) : newsletters.length === 0 ? (
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
                className="group overflow-hidden rounded-2xl border border-gray-800 transition hover:border-gray-600"
              >

                {newsletter.cover_image && (
                  <Link
                    to={`/newsletters/${newsletter.id}`}
                    className="block aspect-[2/1] overflow-hidden bg-neutral-900"
                  >
                    <img
                      src={newsletter.cover_image}
                      alt=""
                      loading="lazy"
                      referrerPolicy="no-referrer"
                      onError={(event) => {
                        event.currentTarget.parentElement.style.display = "none"
                      }}
                      className="h-full w-full object-cover transition duration-500 group-hover:scale-[1.03]"
                    />
                  </Link>
                )}

                <div className="p-8">

                <div className="flex items-center justify-between gap-4">
                  <span className="text-sm text-gray-500">
                    {formatDate(newsletter.published_at || newsletter.created_at)}
                  </span>

                  <span className="rounded-full border border-gray-800 px-3 py-1 text-xs text-gray-400">
                    AINow
                  </span>
                </div>

                <h2 className="mt-8 text-2xl font-bold transition group-hover:text-gray-300">
                  {newsletter.headline || newsletter.title}
                </h2>

                <p className="mt-4 line-clamp-3 leading-7 text-gray-400">
                  {newsletter.intro ||
                    "A curated edition of the latest AI news, research, trends and tools."}
                </p>

                <Link
                  to={`/newsletters/${newsletter.id}`}
                  className="mt-8 inline-block font-medium text-white hover:text-gray-300"
                >
                  Read Newsletter →
                </Link>

                </div>

              </article>
            ))}

          </div>
        )}

      </div>
    </main>
  )
}

export default Newsletters