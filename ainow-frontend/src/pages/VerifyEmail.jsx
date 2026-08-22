import { Link, useLocation } from "react-router-dom"

function VerifyEmail() {
  const location = useLocation()

  const email = location.state?.email || "your email address"

  return (
    <div className="flex min-h-screen items-center justify-center bg-black px-6 text-white">

      <div className="w-full max-w-md text-center">

        {/* Icon */}
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full border border-gray-800 text-2xl">
          ✉
        </div>

        <h1 className="mt-8 text-4xl font-bold">
          Check your inbox.
        </h1>

        <p className="mt-4 leading-7 text-gray-400">
          We've sent a verification link to
        </p>

        <p className="mt-2 font-medium text-white">
          {email}
        </p>

        <p className="mt-6 text-sm leading-6 text-gray-500">
          Click the link in the email to verify your account.
          Once your email is verified, you'll be able to login
          to AINow.
        </p>

        <div className="mt-10 space-y-4">

          <button
            className="w-full rounded-xl border border-gray-800 py-3 text-gray-300 hover:bg-gray-900"
          >
            Resend Verification Email
          </button>

          <Link
            to="/login"
            className="block text-sm text-gray-400 hover:text-white"
          >
            Back to Login
          </Link>

        </div>

      </div>

    </div>
  )
}

export default VerifyEmail