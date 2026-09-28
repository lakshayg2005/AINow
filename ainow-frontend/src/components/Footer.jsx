import { Link } from "react-router-dom"
import { useAuth } from "../context/auth"

function Footer() {
  const { isAuthenticated } = useAuth()

  return (
    <footer className="border-t border-gray-800 bg-black text-white">
      <div className="mx-auto max-w-7xl px-6 py-12">

        <div className="flex flex-col justify-between gap-8 md:flex-row">

          {/* Brand */}
          <div>
            <h2 className="text-2xl font-bold">
              AINow
            </h2>

            <p className="mt-3 max-w-sm text-sm leading-6 text-gray-500">
              Your concise source for the latest developments
              in artificial intelligence.
            </p>
          </div>

          {/* Links */}
          <div className="flex gap-12">
            <div>
              <h3 className="text-sm font-semibold">
                Explore
              </h3>

              <div className="mt-4 space-y-3 text-sm text-gray-500">
                <Link to="/" className="block hover:text-white">
                  Home
                </Link>

                <Link to="/about" className="block hover:text-white">
                  About
                </Link>

                <Link to="/newsletters" className="block hover:text-white">
                  Newsletters
                </Link>
              </div>
            </div>

            <div>
              <h3 className="text-sm font-semibold">
                Account
              </h3>

              <div className="mt-4 space-y-3 text-sm text-gray-500">
                {isAuthenticated ? (
                  <Link to="/dashboard" className="block hover:text-white">
                    Dashboard
                  </Link>
                ) : (
                  <>
                    <Link to="/register" className="block hover:text-white">
                      Subscribe
                    </Link>

                    <Link to="/login" className="block hover:text-white">
                      Login
                    </Link>
                  </>
                )}
              </div>
            </div>
          </div>

        </div>

        <div className="mt-12 border-t border-gray-800 pt-6 text-sm text-gray-600">
          © {new Date().getFullYear()} AINow. All rights reserved.
        </div>

      </div>
    </footer>
  )
}

export default Footer
