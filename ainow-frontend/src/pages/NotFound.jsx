import { Link } from "react-router-dom"

// Unknown URLs (including the removed /contact page).
function NotFound() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-black px-6 pb-24 text-white">
      <div className="text-center">
        <p className="text-sm uppercase tracking-widest text-gray-500">404</p>
        <h1 className="mt-4 text-4xl font-bold">Page not found</h1>
        <p className="mt-4 text-gray-400">This page doesn't exist or has moved.</p>
        <div className="mt-8 flex justify-center gap-4">
          <Link to="/" className="rounded-xl bg-white px-6 py-3 font-semibold text-black hover:bg-gray-200">
            Home
          </Link>
          <Link to="/newsletters" className="rounded-xl border border-gray-700 px-6 py-3 font-semibold hover:bg-gray-900">
            Newsletters
          </Link>
        </div>
      </div>
    </main>
  )
}

export default NotFound
