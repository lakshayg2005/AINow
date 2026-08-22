import { useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"
import { getNewsletter } from "../services/api"

function NewsletterDetail() {
  const { id } = useParams()

  const [newsletter, setNewsletter] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  useEffect(() => {
    async function loadNewsletter() {
      try {
        const data = await getNewsletter(id)
        setNewsletter(data)
      } catch (error) {
        setError(error.message)
      } finally {
        setLoading(false)
      }
    }

    loadNewsletter()
  }, [id])

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-black text-white">
        <p className="text-gray-400">
          Loading newsletter...
        </p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen bg-black px-6 py-24 text-white">
        <p className="text-red-400">{error}</p>

        <Link
          to="/newsletters"
          className="mt-6 inline-block text-gray-300 hover:text-white"
        >
          ← Back to newsletters
        </Link>
      </div>
    )
  }

  return (
    <main className="min-h-screen bg-black px-6 py-24 text-white">
      <article className="mx-auto max-w-4xl">

        <Link
          to="/newsletters"
          className="text-sm text-gray-500 hover:text-white"
        >
          ← Back to newsletters
        </Link>

        <p className="mt-10 text-sm uppercase tracking-widest text-gray-500">
          Newsletter
        </p>

        <h1 className="mt-4 text-5xl font-bold">
          {newsletter.title}
        </h1>

        {newsletter.published_at && (
          <p className="mt-4 text-gray-500">
            {new Date(newsletter.published_at).toLocaleDateString(
              "en-US",
              {
                year: "numeric",
                month: "long",
                day: "numeric",
              }
            )}
          </p>
        )}

        <div
          className="prose prose-invert mt-12 max-w-none"
          dangerouslySetInnerHTML={{
            __html: newsletter.html_content,
          }}
        />

      </article>
    </main>
  )
}

export default NewsletterDetail