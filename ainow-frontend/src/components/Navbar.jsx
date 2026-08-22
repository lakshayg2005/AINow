import { Link } from "react-router-dom"
import { useAuth } from "../context/AuthContext"

function Navbar() {
  const { isAuthenticated, user, logout } = useAuth()

  return (
    <nav className="border-b border-gray-800 bg-black py-4 text-white">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6">
        <Link to="/" className="text-xl font-bold">
          AINow 
        </Link>

        <div className="hidden items-center gap-8 md:flex">
          <Link
            to="/"
            className="text-gray-300 hover:text-white"
          >
            Home
          </Link>

          <Link
            to="/about"
            className="text-gray-300 hover:text-white"
          >
            About
          </Link>

          <Link
            to="/newsletters"
            className="text-gray-300 hover:text-white"
          >
            Newsletters
          </Link>

          <Link
            to="/contact"
            className="text-gray-300 hover:text-white"
          >
            Contact
          </Link>
        </div>

        {isAuthenticated ? (
          <div className="flex items-center gap-4">
            <Link
              to="/dashboard"
              className="text-sm text-gray-300 hover:text-white"
            >
              {user?.name}
            </Link>

            <button
              onClick={logout}
              className="rounded-lg border border-gray-700 px-4 py-2 text-sm font-medium text-white hover:bg-gray-900"
            >
              Logout
            </button>
          </div>
        ) : (
          <Link
            to="/login"
            className="rounded-lg bg-white px-5 py-2 font-medium text-black hover:bg-gray-200"
          >
            Login
          </Link>
        )}
      </div>
    </nav>
  )
}

export default Navbar