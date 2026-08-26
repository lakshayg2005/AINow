import { useEffect, useState } from "react"
import { Link, useNavigate } from "react-router-dom"

import {
  loginUser,
  resendVerification,
} from "../services/api"

function Login() {
  const navigate = useNavigate()

  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")

  const [loading, setLoading] = useState(false)
  const [resending, setResending] = useState(false)

  const [error, setError] = useState("")
  const [success, setSuccess] = useState("")

  const [verificationRequired, setVerificationRequired] =
    useState(false)

  const [cooldown, setCooldown] = useState(0)

  // ---------------------------------------------------------
  // RESEND COUNTDOWN
  // ---------------------------------------------------------

  useEffect(() => {
    if (cooldown <= 0) {
      return
    }

    const timer = setInterval(() => {
      setCooldown((current) =>
        Math.max(current - 1, 0)
      )
    }, 1000)

    return () => clearInterval(timer)
  }, [cooldown])

  // ---------------------------------------------------------
  // LOGIN
  // ---------------------------------------------------------

  async function handleSubmit(event) {
    event.preventDefault()

    setError("")
    setSuccess("")
    setLoading(true)

    try {
      const data = await loginUser({
        email,
        password,
      })

      // Login succeeded, so verification is no longer required.
      setVerificationRequired(false)

      /*
       * Keep this only if loginUser() does not already
       * store the token in localStorage.
       */
      localStorage.setItem(
        "access_token",
        data.access_token
      )

      navigate("/dashboard")

    } catch (err) {
      const message =
        err.message ||
        "Login failed."

      setError(message)

      // Backend returns this when the account is unverified.
      if (
        message
          .toLowerCase()
          .includes("verify your email")
      ) {
        setVerificationRequired(true)
      }

    } finally {
      setLoading(false)
    }
  }

  // ---------------------------------------------------------
  // RESEND VERIFICATION
  // ---------------------------------------------------------

  async function handleResend() {
    if (cooldown > 0) {
      return
    }

    setError("")
    setSuccess("")
    setResending(true)

    try {
      const data = await resendVerification(email)

      setSuccess(data.message)

      // IMPORTANT:
      // Keep the resend button visible.
      setVerificationRequired(true)

      // Start 60-second frontend cooldown.
      setCooldown(60)

    } catch (err) {
      setError(
        err.message ||
        "Unable to resend verification email."
      )
    } finally {
      setResending(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-black px-6 text-white">
      <div className="w-full max-w-md">

        <h1 className="text-4xl font-bold">
          Welcome back.
        </h1>

        <p className="mt-3 text-gray-400">
          Login to your AINow account.
        </p>

        {/* ERROR MESSAGE */}

        {error && (
          <div className="mt-6 rounded-xl border border-red-900 bg-red-950/30 p-4 text-sm text-red-400">
            {error}
          </div>
        )}

        {/* SUCCESS MESSAGE */}

        {success && (
          <div className="mt-6 rounded-xl border border-green-900 bg-green-950/30 p-4 text-sm text-green-400">
            {success}
          </div>
        )}

        {/* LOGIN FORM */}

        <form
          onSubmit={handleSubmit}
          className="mt-10 space-y-5"
        >
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(event) =>
              setEmail(event.target.value)
            }
            className="w-full rounded-xl border border-gray-800 bg-transparent px-5 py-4 outline-none focus:border-white"
            required
          />

          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(event) =>
              setPassword(event.target.value)
            }
            className="w-full rounded-xl border border-gray-800 bg-transparent px-5 py-4 outline-none focus:border-white"
            required
          />

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-xl bg-white py-4 font-semibold text-black disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading
              ? "Logging in..."
              : "Login"}
          </button>
        </form>

        {/* RESEND VERIFICATION */}

        {verificationRequired && (
          <button
            type="button"
            onClick={handleResend}
            disabled={
              resending ||
              cooldown > 0 ||
              !email
            }
            className="mt-5 w-full rounded-xl border border-gray-700 py-3 text-sm text-white hover:bg-gray-900 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {resending
              ? "Sending..."
              : cooldown > 0
                ? `Resend available in ${cooldown}s`
                : "Resend Verification Email"}
          </button>
        )}

        <p className="mt-6 text-center text-sm text-gray-500">
          Don't have an account?{" "}

          <Link
            to="/register"
            className="text-white hover:underline"
          >
            Create one
          </Link>
        </p>

      </div>
    </div>
  )
}

export default Login