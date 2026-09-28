import { useState } from "react"
import { Link, NavLink } from "react-router-dom"
import { useAuth } from "../context/auth"

const LINKS = [
  { to: "/", label: "Home", end: true },
  { to: "/about", label: "About" },
  { to: "/newsletters", label: "Newsletters" },
]

function navClass({ isActive }) {
  return isActive ? "text-white" : "text-gray-400 hover:text-white"
}

function Navbar() {
  const { isAuthenticated, user, logout } = useAuth()
  const [open, setOpen] = useState(false)

  const close = () => setOpen(false)

  return (
    <nav className="border-b border-gray-800 bg-black py-4 text-white">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-6">
        <Link to="/" onClick={close} className="text-xl font-bold">
          AINow
        </Link>

        <div className="hidden items-center gap-8 md:flex">
          {LINKS.map((link) => (
            <NavLink key={link.to} to={link.to} end={link.end} className={navClass}>
              {link.label}
            </NavLink>
          ))}
        </div>

        <div className="flex items-center gap-3 md:gap-4">
          {isAuthenticated ? (
            <>
              {user?.is_admin && (
                <NavLink
                  to="/admin"
                  className={({ isActive }) =>
                    `hidden text-sm font-medium sm:inline ${isActive ? "text-indigo-200" : "text-indigo-300 hover:text-indigo-200"}`
                  }
                >
                  Admin
                </NavLink>
              )}

              <NavLink to="/dashboard" className={({ isActive }) => `hidden max-w-[10rem] truncate text-sm sm:inline ${navClass({ isActive })}`}>
                {user?.name}
              </NavLink>

              <button
                type="button"
                onClick={() => {
                  close()
                  logout()
                }}
                className="rounded-lg border border-gray-700 px-4 py-2 text-sm font-medium text-white hover:bg-gray-900"
              >
                Logout
              </button>
            </>
          ) : (
            <Link
              to="/login"
              onClick={close}
              className="rounded-lg bg-white px-5 py-2 font-medium text-black hover:bg-gray-200"
            >
              Login
            </Link>
          )}

          <button
            type="button"
            onClick={() => setOpen((value) => !value)}
            aria-expanded={open}
            aria-controls="mobile-menu"
            aria-label={open ? "Close menu" : "Open menu"}
            className="rounded-lg border border-gray-800 p-2 text-gray-300 hover:text-white md:hidden"
          >
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
              {open ? <path d="M5 5l10 10M15 5L5 15" /> : <path d="M3 6h14M3 10h14M3 14h14" />}
            </svg>
          </button>
        </div>
      </div>

      {open && (
        <div id="mobile-menu" className="mx-auto mt-4 flex max-w-7xl flex-col gap-1 border-t border-gray-800 px-6 pt-3 md:hidden">
          {LINKS.map((link) => (
            <NavLink key={link.to} to={link.to} end={link.end} onClick={close} className={(state) => `py-2 ${navClass(state)}`}>
              {link.label}
            </NavLink>
          ))}

          {isAuthenticated && (
            <NavLink to="/dashboard" onClick={close} className={(state) => `py-2 ${navClass(state)}`}>
              Dashboard
            </NavLink>
          )}

          {user?.is_admin && (
            <NavLink to="/admin" onClick={close} className="py-2 text-indigo-300 hover:text-indigo-200">
              Admin
            </NavLink>
          )}
        </div>
      )}
    </nav>
  )
}

export default Navbar
