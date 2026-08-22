const API_BASE_URL = "http://127.0.0.1:8000"

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

export async function checkBackend() {
  const response = await fetch("http://127.0.0.1:8000/health")

  if (!response.ok) {
    throw new Error("Backend is unavailable")
  }

  return response.json()
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