import { useEffect, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"

const API_BASE_URL = "http://127.0.0.1:8000"

function VerifyEmail() {
  const [searchParams] = useSearchParams()

  const [status, setStatus] = useState("verifying")
  const [message, setMessage] = useState("")

  useEffect(() => {
    const token = searchParams.get("token")

    if (!token) {
      setStatus("error")
      setMessage("Verification token is missing.")
      return
    }

    let cancelled = false

    async function verify() {
      try {
        const response = await fetch(
          `${API_BASE_URL}/auth/verify-email?token=${encodeURIComponent(token)}`
        )

        const data = await response.json()

        if (cancelled) {
          return
        }

        if (!response.ok) {
          throw new Error(
            data.detail ||
            "Email verification failed."
          )
        }

        setStatus("success")
        setMessage(data.message)
      } catch (error) {
        if (cancelled) {
          return
        }

        setStatus("error")
        setMessage(
          error.message ||
          "Email verification failed."
        )
      }
    }

    verify()

    return () => {
      cancelled = true
    }
  }, [searchParams])

  return (
    <main className="flex min-h-screen items-center justify-center bg-black px-6 text-white">
      <div className="w-full max-w-md text-center">

        {status === "verifying" && (
          <>
            <h1 className="text-4xl font-bold">
              Verifying your email...
            </h1>

            <p className="mt-4 text-gray-400">
              Please wait.
            </p>
          </>
        )}

        {status === "success" && (
          <>
            <h1 className="text-4xl font-bold">
              Email verified.
            </h1>

            <p className="mt-4 text-gray-400">
              {message}
            </p>

            <Link
              to="/login"
              className="mt-8 inline-block rounded-xl bg-white px-7 py-3 font-semibold text-black"
            >
              Go to Login
            </Link>
          </>
        )}

        {status === "error" && (
          <>
            <h1 className="text-4xl font-bold">
              Verification failed.
            </h1>

            <p className="mt-4 text-gray-400">
              {message}
            </p>

            <Link
              to="/register"
              className="mt-8 inline-block text-white hover:underline"
            >
              Back to Register
            </Link>
          </>
        )}

      </div>
    </main>
  )
}

export default VerifyEmail