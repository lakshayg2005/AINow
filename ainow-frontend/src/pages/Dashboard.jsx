import { useEffect, useState } from "react"
import { useAuth } from "../context/AuthContext"
import {
  getSubscription,
  subscribeUser,
  cancelSubscription,
} from "../services/api"


async function handleSubscribe() {
  const token = localStorage.getItem("access_token")

  try {
    const data = await subscribeUser(token)
    setSubscription(data)
  } catch (error) {
    setSubscriptionError(error.message)
  }
}


async function handleCancelSubscription() {
  const token = localStorage.getItem("access_token")

  try {
    const data = await cancelSubscription(token)
    setSubscription(data)
  } catch (error) {
    setSubscriptionError(error.message)
  }
}

function Dashboard() {
  const { user, loading } = useAuth()

 const [subscription, setSubscription] = useState(null)
 const [subscriptionLoading, setSubscriptionLoading] = useState(true)
 const [subscriptionError, setSubscriptionError] = useState("")

  // if (loading) {
  //   return (
  //     <div className="flex min-h-screen items-center justify-center bg-black text-white">
  //       <p className="text-gray-400">Loading dashboard...</p>
  //     </div>
  //   )
  // }

  // if (!user) {
  //   return null
  // }
  useEffect(() => {
    async function loadSubscription() {
      const token = localStorage.getItem("access_token")
  
      if (!token) {
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
      : subscription?.status === "active"
        ? "Active"
        : "Not Active"}
  </h2>

  {!subscriptionLoading && subscription?.status !== "active" && (
    <button
      onClick={handleSubscribe}
      className="mt-6 rounded-xl bg-white px-5 py-3 font-semibold text-black hover:bg-gray-200"
    >
      Subscribe
    </button>
  )}

  {!subscriptionLoading && subscription?.status === "active" && (
    <button
      onClick={handleCancelSubscription}
      className="mt-6 rounded-xl border border-gray-700 px-5 py-3 font-semibold text-white hover:bg-gray-900"
    >
      Cancel Subscription
    </button>
  )}
</div>

          <div className="rounded-2xl border border-gray-800 p-6">
            <p className="text-gray-500">Newsletter</p>
            <h2 className="mt-3 text-2xl font-bold">
              Weekly AI
            </h2>
          </div>

          <div className="rounded-2xl border border-gray-800 p-6">
            <p className="text-gray-500">Account</p>
            <h2 className="mt-3 text-2xl font-bold">
              {user.is_email_verified ? "Verified" : "Not Verified"}
            </h2>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Dashboard