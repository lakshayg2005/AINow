import { useCallback, useEffect, useState } from "react"
import { getCurrentUser } from "../services/api"
import { AuthContext } from "./auth"

function hasToken() {
  return Boolean(localStorage.getItem("access_token"))
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  // Without a stored token there is nothing to load.
  const [loading, setLoading] = useState(hasToken)

  const fetchUser = useCallback(() => {
    const token = localStorage.getItem("access_token")

    if (!token) {
      setUser(null)
      setLoading(false)
      return Promise.resolve()
    }

    return getCurrentUser(token)
      .then(setUser)
      .catch(() => {
        localStorage.removeItem("access_token")
        setUser(null)
      })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!hasToken()) return

    let cancelled = false

    getCurrentUser(localStorage.getItem("access_token"))
      .then((currentUser) => {
        if (!cancelled) setUser(currentUser)
      })
      .catch(() => {
        if (!cancelled) {
          localStorage.removeItem("access_token")
          setUser(null)
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [])

  function logout() {
    localStorage.removeItem("access_token")
    setUser(null)
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        isAuthenticated: !!user,
        logout,
        refreshUser: fetchUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}
