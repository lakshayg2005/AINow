import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { getNewsletters } from "../services/api"

function formatDate(value) {
  if (!value) return ""

  return new Date(value).toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  })
}

// The most recent published issue, shown on the home page.
function NewsletterPreview() {
  const [latest, setLatest] = useState(null)
  const [state, setState] = useState("loading")

  useEffect(() => {
    let cancelled = false

    getNewsletters({ limit: 1 })
      .then((issues) => {
        if (cancelled) return
        setLatest(issues[0] || null)
        setState(issues[0] ? "ready" : "empty")
      })
      .catch(() => {
        if (!cancelled) setState("empty")
      })

    return () => {
      cancelled = true
    }
  }, [])

  return (
    <section className="bg-black py-24 text-white">
      <div className="mx-auto max-w-7xl px-6">

        <div className="flex flex-col justify-between gap-6 md:flex-row md:items-end">
          <div>
            <p className="text-sm font-semibold uppercase tracking-widest text-gray-500">
              Latest Edition
            </p>

            <h2 className="mt-4 text-4xl font-bold md:text-5xl">
              What's happening in AI?
            </h2>
          </div>

          <Link to="/newsletters" className="w-fit text-gray-400 transition hover:text-white">
            View all newsletters →
          </Link>
        </div>

        {state === "loading" && (
          <div className="mt-14 h-[350px] animate-pulse rounded-3xl border border-gray-800 bg-neutral-950" />
        )}

        {state === "empty" && (
          <div className="mt-14 rounded-3xl border border-gray-800 p-8 md:p-12">
            <h3 className="text-3xl font-bold">The first issue is on its way.</h3>
            <p className="mt-4 max-w-xl leading-7 text-gray-400">
              Create an account and subscribe to get it in your inbox the moment it's published.
            </p>
            <Link
              to="/register"
              className="mt-8 inline-block rounded-xl bg-white px-6 py-3 font-semibold text-black hover:bg-gray-200"
            >
              Get the Newsletter
            </Link>
          </div>
        )}

        {state === "ready" && latest && (
          <Link
            to={`/newsletters/${latest.id}`}
            className="group mt-14 block overflow-hidden rounded-3xl border border-gray-800 transition hover:border-gray-600"
          >
            <div className="grid md:grid-cols-2">

              <div className="flex flex-col p-8 md:p-12">
                <span className="w-fit rounded-full border border-gray-700 px-3 py-1 text-xs uppercase text-gray-400">
                  {formatDate(latest.published_at || latest.created_at)}
                </span>

                <h3 className="mt-8 text-3xl font-bold md:text-4xl">
                  {latest.headline || latest.title}
                </h3>

                {latest.intro && (
                  <p className="mt-6 line-clamp-4 leading-7 text-gray-400">
                    {latest.intro}
                  </p>
                )}

                <span className="mt-8 w-fit rounded-xl bg-white px-6 py-3 font-semibold text-black transition group-hover:bg-gray-200">
                  Read Newsletter
                </span>
              </div>

              <div className="relative min-h-[280px] overflow-hidden bg-gradient-to-br from-indigo-950 via-neutral-900 to-black md:min-h-[350px]">
                {latest.cover_image ? (
                  <img
                    src={latest.cover_image}
                    alt=""
                    referrerPolicy="no-referrer"
                    onError={(event) => {
                      event.currentTarget.style.display = "none"
                    }}
                    className="absolute inset-0 h-full w-full object-cover transition duration-500 group-hover:scale-[1.03]"
                  />
                ) : (
                  <div className="flex h-full items-center justify-center text-7xl font-bold text-white/80">
                    AI
                  </div>
                )}
              </div>

            </div>
          </Link>
        )}

      </div>
    </section>
  )
}

export default NewsletterPreview
