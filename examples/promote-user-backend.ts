const BACKEND_BASE_URL = process.env.VITE_API_URL ;

function normalizeRole(role: string) {
  const normalized = role.toLowerCase().replace(/[-\s]/g, "_");
  return normalized === "superadmin" ? "super-admin" : normalized;
}

export async function promoteUserViaBackend(email: string, role: string, token: string) {
  const normalizedRole = normalizeRole(role);
  const url = `${BACKEND_BASE_URL}/promote_user?email=${encodeURIComponent(email)}&role=${encodeURIComponent(normalizedRole)}`;

  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `Promotion failed: ${response.statusText}`);
  }

  return response.json();
}

// Example usage:
//
// const token = localStorage.getItem("access_token");
// await promoteUserViaBackend("jonathan@gmail.com", "super-admin", token);
