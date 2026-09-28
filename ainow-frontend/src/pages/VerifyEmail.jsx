import { useEffect, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { verifyEmail } from "../services/api"

function VerifyEmail() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get("token")

  const [result, setResult] = useState(null)

  // A link without a token fails without calling the API.
  const status = !token ? "error" : result?.status || "verifying"
  const message = !token ? "Verification token is missing." : result?.message || ""

  useEffect(() => {
    if (!token) return undefined

    let cancelled = false

    verifyEmail(token)
      .then((data) => {
        if (!cancelled) setResult({ status: "success", message: data.message })
      })
      .catch((error) => {
        if (!cancelled) {
          setResult({ status: "error", message: error.message || "Email verification failed." })
        }
      })

    return () => {
      cancelled = true
    }
  }, [token])

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