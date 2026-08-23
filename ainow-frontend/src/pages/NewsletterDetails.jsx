import { useEffect, useState } from "react"
import {
  Link,
  useParams,
} from "react-router-dom"
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
      } catch (err) {
        setError(
          err.message ||
          "Unable to load newsletter."
        )
      } finally {
        setLoading(false)
      }
    }

    loadNewsletter()
  }, [id])

  if (loading) {
    return (
      <main className="min-h-screen bg-black px-6 py-24 text-white">
        <div className="mx-auto max-w-5xl">
          <p className="text-gray-400">
            Loading newsletter...
          </p>
        </div>
      </main>
    )
  }

  if (error || !newsletter) {
    return (
      <main className="min-h-screen bg-black px-6 py-24 text-white">
        <div className="mx-auto max-w-5xl">
          <p className="text-red-400">
            {error || "Newsletter not found."}
          </p>

          <Link
            to="/newsletters"
            className="mt-6 inline-block text-white"
          >
            ← Back to newsletters
          </Link>
        </div>
      </main>
    )
  }

  return (
    <main className="min-h-screen bg-neutral-200 py-8">

      <div className="mx-auto max-w-[1100px] px-4">

        <div className="mb-6 flex items-center justify-between">
          <Link
            to="/newsletters"
            className="text-sm font-medium text-black hover:underline"
          >
            ← Back to newsletters
          </Link>

          <span className="text-sm text-gray-600">
            AINow
          </span>
        </div>

        <div className="overflow-hidden rounded-2xl bg-white shadow-xl">

          <iframe
            title={newsletter.title}
            srcDoc={newsletter.html_content}
            className="block h-[calc(100vh-120px)] min-h-[900px] w-full border-0"
          />

        </div>

      </div>

    </main>
  )
}

export default NewsletterDetail