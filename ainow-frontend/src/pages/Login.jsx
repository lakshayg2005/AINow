import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { loginUser } from "../services/api"
import { useAuth } from "../context/AuthContext"

function Login() {
  const navigate = useNavigate()
   
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  const { refreshUser } = useAuth()

  async function handleSubmit(event) {
    event.preventDefault()

    setError("")
    setLoading(true)

    try {
      const data = await loginUser({
        email,
        password,
      })

      localStorage.setItem("access_token", data.access_token)

      await refreshUser()
      
      navigate("/dashboard")
    } catch (error) {
      setError(error.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-black px-6 text-white">
      <div className="w-full max-w-md">
        <h1 className="text-4xl font-bold">Welcome back.</h1>

        <p className="mt-3 text-gray-400">
          Login to your AINow account.
        </p>

        <form onSubmit={handleSubmit} className="mt-10 space-y-5">
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className="w-full rounded-xl border border-gray-800 bg-transparent px-5 py-4 outline-none focus:border-white"
            required
          />

          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="w-full rounded-xl border border-gray-800 bg-transparent px-5 py-4 outline-none focus:border-white"
            required
          />

          {error && (
            <p className="rounded-lg border border-red-800 bg-red-950/30 px-4 py-3 text-sm text-red-400">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-xl bg-white py-4 font-semibold text-black hover:bg-gray-200 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? "Logging in..." : "Login"}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-gray-500">
          Don't have an account?{" "}
          <Link to="/register" className="text-white hover:underline">
            Create one
          </Link>
        </p>
      </div>
    </div>
  )
}

export default Login