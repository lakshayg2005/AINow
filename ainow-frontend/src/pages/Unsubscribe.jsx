import { useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { unsubscribeWithToken } from "../services/api"

// Reached from the "Unsubscribe" link in every newsletter. The
// explicit button keeps link scanners (which open every URL in
// an email) from unsubscribing people.
function Unsubscribe() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get("token")

  const [state, setState] = useState("confirm")
  const [message, setMessage] = useState("")

  async function handleUnsubscribe() {
    setState("working")

    try {
      const data = await unsubscribeWithToken(token)
      setMessage(data.message)
      setState("done")
    } catch (err) {
      setMessage(err.message)
      setState("error")
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-black px-6 py-24 text-white">
      <div className="w-full max-w-md rounded-3xl border border-neutral-800 bg-neutral-950 p-8 text-center">
        {!token && (
          <>
            <h1 className="text-2xl font-bold">Invalid link</h1>
            <p className="mt-3 text-neutral-400">This unsubscribe link is missing its token.</p>
          </>
        )}

        {token && (state === "confirm" || state === "working") && (
          <>
            <h1 className="text-2xl font-bold">Unsubscribe from AINow?</h1>
            <p className="mt-3 text-neutral-400">You'll stop receiving the weekly newsletter. You can resubscribe any time from your dashboard.</p>
            <button
              type="button"
              onClick={handleUnsubscribe}
              disabled={state === "working"}
              className="mt-8 w-full rounded-xl bg-white px-5 py-3 font-semibold text-black hover:bg-neutral-200 disabled:opacity-50"
            >
              {state === "working" ? "Unsubscribing…" : "Unsubscribe"}
            </button>
          </>
        )}

        {state === "done" && (
          <>
            <h1 className="text-2xl font-bold">You're unsubscribed</h1>
            <p className="mt-3 text-neutral-400">{message} Sorry to see you go.</p>
          </>
        )}

        {state === "error" && (
          <>
            <h1 className="text-2xl font-bold">Something went wrong</h1>
            <p className="mt-3 text-rose-300">{message}</p>
          </>
        )}

        <Link to="/" className="mt-8 inline-block text-sm text-neutral-400 hover:text-white">
          ← Back to AINow
        </Link>
      </div>
    </main>
  )
}

export default Unsubscribe
