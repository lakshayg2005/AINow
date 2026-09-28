import { useEffect, useState } from "react"
import {
  Link,
  useParams,
  useSearchParams,
} from "react-router-dom"
import IssueView from "../components/issue/IssueView"
import {
  getNewsletter,
  getNewsletterPreview,
} from "../services/api"

function NewsletterDetail() {
  const { id } = useParams()
  const [searchParams] = useSearchParams()
  const isPreview = searchParams.get("preview") === "1"

  const [newsletter, setNewsletter] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  useEffect(() => {
    async function loadNewsletter() {
      try {
        const data = isPreview
          ? await getNewsletterPreview(id)
          : await getNewsletter(id)
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
  }, [id, isPreview])

  if (loading) {
    return (
      <main className="min-h-screen bg-black px-6 py-24 text-white">
        <div className="mx-auto max-w-5xl animate-pulse">
          <div className="h-4 w-32 rounded bg-neutral-800" />
          <div className="mt-8 h-14 w-3/4 rounded bg-neutral-900" />
          <div className="mt-4 h-5 w-2/3 rounded bg-neutral-900" />
          <div className="mt-16 grid gap-6 md:grid-cols-2">
            <div className="h-72 rounded-2xl bg-neutral-900" />
            <div className="h-72 rounded-2xl bg-neutral-900" />
          </div>
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

  // Issues written by the new pipeline carry structured
  // content and get the interactive view.
  if (newsletter.content?.version === 2) {
    return (
      <IssueView
        issue={newsletter}
        isPreview={isPreview && newsletter.status !== "published"}
      />
    )
  }

  // Legacy issues: render the stored HTML.
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
