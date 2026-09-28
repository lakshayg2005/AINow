import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { useAuth } from "../context/auth"
import {
  getSubscription,
  subscribeUser,
  cancelSubscription,
} from "../services/api"

function Dashboard() {
  const { user } = useAuth()

  const [subscription, setSubscription] = useState(null)
  const [subscriptionLoading, setSubscriptionLoading] = useState(true)
  const [subscriptionError, setSubscriptionError] = useState("")
  const [updating, setUpdating] = useState(false)

  useEffect(() => {
    async function loadSubscription() {
      const token = localStorage.getItem("access_token")

      if (!token) {
        setSubscriptionLoading(false)
        return
      }

      try {
        const data = await getSubscription(token)
        setSubscription(data)
      } catch (error) {
        setSubscriptionError(error.message)
      } finally {
        setSubscriptionLoading(false)
      }
    }

    if (user) {
      loadSubscription()
    }
  }, [user])

  // Handlers live inside the component so they can update
  // its state.
  async function updateSubscription(action) {
    const token = localStorage.getItem("access_token")

    setUpdating(true)
    setSubscriptionError("")

    try {
      const data = await action(token)
      setSubscription(data)
    } catch (error) {
      setSubscriptionError(error.message)
    } finally {
      setUpdating(false)
    }
  }

  const isActive = subscription?.status === "active"

  return (
    <div className="min-h-screen bg-black px-6 py-24 text-white">
      <div className="mx-auto max-w-7xl">
        <p className="text-sm uppercase tracking-widest text-gray-500">
          Dashboard
        </p>

        <h1 className="mt-4 text-5xl font-bold">
          Welcome, {user.name}.
        </h1>

        <p className="mt-4 text-gray-400">
          {user.email}
        </p>

        <div className="mt-12 grid gap-6 md:grid-cols-3">
          <div className="rounded-2xl border border-gray-800 p-6">
            <p className="text-gray-500">Subscription</p>

            <h2 className="mt-3 text-2xl font-bold">
              {subscriptionLoading
                ? "Loading..."
                : isActive
                  ? "Active"
                  : "Not Active"}
            </h2>

            {subscription?.message && !subscriptionLoading && (
              <p className="mt-2 text-sm text-gray-400">
                {subscription.message}
              </p>
            )}

            {!subscriptionLoading && !isActive && (
              <button
                onClick={() => updateSubscription(subscribeUser)}
                disabled={updating}
                className="mt-6 rounded-xl bg-white px-5 py-3 font-semibold text-black hover:bg-gray-200 disabled:opacity-50"
              >
                {updating ? "Subscribing..." : "Subscribe"}
              </button>
            )}

            {!subscriptionLoading && isActive && (
              <button
                onClick={() => updateSubscription(cancelSubscription)}
                disabled={updating}
                className="mt-6 rounded-xl border border-gray-700 px-5 py-3 font-semibold text-white hover:bg-gray-900 disabled:opacity-50"
              >
                {updating ? "Canceling..." : "Cancel Subscription"}
              </button>
            )}

            {subscriptionError && (
              <p className="mt-4 text-sm text-red-400">
                {subscriptionError}
              </p>
            )}
          </div>

          <div className="rounded-2xl border border-gray-800 p-6">
            <p className="text-gray-500">Newsletter</p>
            <h2 className="mt-3 text-2xl font-bold">
              Weekly AI
            </h2>
            <Link
              to="/newsletters"
              className="mt-6 inline-block text-sm font-medium text-gray-300 hover:text-white"
            >
              Read past issues →
            </Link>
          </div>

          <div className="rounded-2xl border border-gray-800 p-6">
            <p className="text-gray-500">Account</p>
            <h2 className="mt-3 text-2xl font-bold">
              {user.is_email_verified ? "Verified" : "Not Verified"}
            </h2>
          </div>

          {user.is_admin && (
            <Link
              to="/admin"
              className="rounded-2xl border border-indigo-500/40 bg-indigo-500/5 p-6 transition hover:border-indigo-400 md:col-span-3"
            >
              <p className="text-indigo-300">Admin</p>
              <h2 className="mt-3 text-2xl font-bold">
                Newsroom →
              </h2>
              <p className="mt-2 text-sm text-gray-400">
                Fetch news, generate and review drafts, publish to subscribers.
              </p>
            </Link>
          )}
        </div>
      </div>
    </div>
  )
}

export default Dashboard
