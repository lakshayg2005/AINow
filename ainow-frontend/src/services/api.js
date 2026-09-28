// Set VITE_API_URL in .env for a deployed backend.
const API_BASE_URL = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "")

export async function registerUser(userData) {
  const response = await fetch(`${API_BASE_URL}/auth/register`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(userData),
  })

  const data = await response.json()

  if (!response.ok) {
    throw new Error(data.detail || "Registration failed")
  }

  return data
}


export async function loginUser(credentials) {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(credentials),
  })

  const data = await response.json()

  if (!response.ok) {
    throw new Error(data.detail || "Login failed")
  }

  return data
}


export async function getCurrentUser(token) {
  const response = await fetch(`${API_BASE_URL}/auth/me`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  })

  const data = await response.json()

  if (!response.ok) {
    throw new Error(data.detail || "Failed to fetch user")
  }

  return data
}

export async function verifyEmail(token) {
  const response = await fetch(
    `${API_BASE_URL}/auth/verify-email?token=${encodeURIComponent(token)}`
  )

  const data = await response.json().catch(() => ({}))

  if (!response.ok) {
    throw new Error(data.detail || "Email verification failed.")
  }

  return data
}

export async function getSubscription(token) {
  const response = await fetch(
    `${API_BASE_URL}/subscriptions/me`,
    {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  )

  const data = await response.json()

  if (!response.ok) {
    throw new Error(data.detail || "Failed to fetch subscription")
  }

  return data
}


export async function subscribeUser(token) {
  const response = await fetch(
    `${API_BASE_URL}/subscriptions`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  )

  const data = await response.json()

  if (!response.ok) {
    throw new Error(data.detail || "Failed to subscribe")
  }

  return data
}


export async function cancelSubscription(token) {
  const response = await fetch(
    `${API_BASE_URL}/subscriptions`,
    {
      method: "DELETE",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  )

  const data = await response.json()

  if (!response.ok) {
    throw new Error(data.detail || "Failed to cancel subscription")
  }

  return data
}


export async function getNewsletters({ limit } = {}) {
  const response = await fetch(
    `${API_BASE_URL}/newsletters${limit ? `?limit=${limit}` : ""}`
  )

  if (!response.ok) {
    throw new Error(
      "Failed to fetch newsletters"
    )
  }

  return response.json()
}


export async function getNewsletter(
  newsletterId
) {
  const response = await fetch(
    `${API_BASE_URL}/newsletters/${newsletterId}`
  )

  if (!response.ok) {
    throw new Error(
      "Failed to fetch newsletter"
    )
  }

  return response.json()
}

export async function searchNewsletters(query, { signal } = {}) {
  const response = await fetch(
    `${API_BASE_URL}/newsletters/search?q=${encodeURIComponent(query)}`,
    { signal }
  )

  if (!response.ok) {
    throw new Error("Search failed")
  }

  return response.json()
}

export async function resendVerification(email) {
  const response = await fetch(
    `${API_BASE_URL}/auth/resend-verification`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        email,
      }),
    }
  )

  const data = await response.json()

  if (!response.ok) {
    throw new Error(
      data.detail ||
      "Failed to resend verification email."
    )
  }

  return data
}

// ---------------------------------------------------------
// Authenticated requests
// ---------------------------------------------------------

async function authRequest(path, { method = "GET", body } = {}) {
  const token = localStorage.getItem("access_token")

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  const data = await response.json().catch(() => ({}))

  if (!response.ok) {
    throw new Error(
      (typeof data.detail === "string" && data.detail) ||
      `Request failed (${response.status})`
    )
  }

  return data
}

// Drafts are admin-only.
export function getNewsletterPreview(newsletterId) {
  return authRequest(`/newsletters/${newsletterId}/preview`)
}

// ---------------------------------------------------------
// Admin
// ---------------------------------------------------------

export function getAdminOverview() {
  return authRequest("/admin/overview")
}

export function getAdminIssues() {
  return authRequest("/admin/issues")
}

export function startIngestJob() {
  return authRequest("/admin/jobs/ingest", { method: "POST" })
}

export function startComposeJob(days = 7) {
  return authRequest("/admin/jobs/compose", { method: "POST", body: { days } })
}

export function sendTestEmail(issueId, email) {
  return authRequest(`/admin/issues/${issueId}/test-send`, {
    method: "POST",
    body: email ? { email } : {},
  })
}

export function publishIssue(issueId) {
  return authRequest(`/admin/issues/${issueId}/publish`, { method: "POST" })
}

export function retryFailedDeliveries(issueId) {
  return authRequest(`/admin/issues/${issueId}/retry-failed`, { method: "POST" })
}

// Re-checks a draft's images and runs the quality review again.
export function recheckIssue(issueId) {
  return authRequest(`/admin/issues/${issueId}/recheck`, { method: "POST" })
}

export function deleteDraft(issueId) {
  return authRequest(`/admin/issues/${issueId}`, { method: "DELETE" })
}

// ---------------------------------------------------------
// Unsubscribe (no login; token from the email link)
// ---------------------------------------------------------

export async function unsubscribeWithToken(token) {
  const response = await fetch(`${API_BASE_URL}/subscriptions/unsubscribe`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token }),
  })

  const data = await response.json().catch(() => ({}))

  if (!response.ok) {
    throw new Error(data.detail || "Unsubscribe failed.")
  }

  return data
}
