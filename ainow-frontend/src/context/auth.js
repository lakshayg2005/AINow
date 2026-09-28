import { createContext, useContext } from "react"

// Kept apart from AuthProvider so React fast refresh works.
export const AuthContext = createContext(null)

export function useAuth() {
  return useContext(AuthContext)
}
