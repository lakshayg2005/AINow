import { useEffect, useState } from "react"
import { Link } from "react-router-dom"

import {
  registerUser,
  resendVerification,
} from "../services/api"

function Register() {
  const [name, setName] = useState("")
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
  // REGISTER
  // ---------------------------------------------------------

  async function handleSubmit(event) {
    event.preventDefault()

    setError("")
    setSuccess("")
    setLoading(true)

    try {
      const data = await registerUser({
        name,
        email,
        password,
      })

      setSuccess(
        data.message ||
        "Account created successfully. Please verify your email."
      )

      // User now needs to verify the email.
      setVerificationRequired(true)

      // Start resend cooldown because the first email
      // has just been sent.
      setCooldown(60)

    } catch (err) {
      setError(
        err.message ||
        "Registration failed."
      )
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

      // Keep button visible after successful resend.
      setVerificationRequired(true)

      // Start new 60-second countdown.
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
          Join AINow.
        </h1>

        <p className="mt-3 text-gray-400">
          Start receiving the latest AI updates.
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

        {/* REGISTRATION FORM */}

        <form
          onSubmit={handleSubmit}
          className="mt-10 space-y-5"
        >
          <input
            type="text"
            placeholder="Name"
            value={name}
            onChange={(event) =>
              setName(event.target.value)
            }
            className="w-full rounded-xl border border-gray-800 bg-transparent px-5 py-4 outline-none focus:border-white"
            required
            minLength={2}
            maxLength={100}
          />

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
            minLength={8}
            maxLength={128}
          />

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-xl bg-white py-4 font-semibold text-black disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading
              ? "Creating Account..."
              : "Create Account"}
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
                : "Didn't receive the email? Resend Verification"}
          </button>
        )}

        <p className="mt-6 text-center text-sm text-gray-500">
          Already have an account?{" "}

          <Link
            to="/login"
            className="text-white hover:underline"
          >
            Login
          </Link>
        </p>

      </div>
    </div>
  )
}

export default Register