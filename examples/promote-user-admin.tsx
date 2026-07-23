// Replace your current Supabase `user_roles` insert logic with this helper.
// This avoids sending `super-admin` to the DB directly and avoids Supabase RLS issues.

const BACKEND_BASE_URL = import.meta.env.VITE_API_URL;

function normalizeRole(role: string) {
  const normalized = role.toLowerCase().replace(/[-\s]/g, "_");
  return normalized === "superadmin" ? "super-admin" : normalized;
}

export async function promoteUserToRole(email: string, role: string, token: string) {
  const response = await fetch(`${BACKEND_BASE_URL}/promote_user`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({
      email,
      role: normalizeRole(role),
    }),
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `Promotion failed: ${response.statusText}`);
  }

  return response.json();
}

export async function onMakeAdminClick(email: string) {
  const token = window.localStorage.getItem("access_token");
  if (!token) throw new Error("Admin auth token missing.");
  return promoteUserToRole(email, "admin", token);
}

export async function onMakeSuperAdminClick(email: string) {
  const token = window.localStorage.getItem("access_token");
  if (!token) throw new Error("Admin auth token missing.");
  return promoteUserToRole(email, "super-admin", token);
}

// Example usage in JSX:
// <button onClick={() => onMakeAdminClick(user.email)}>Make admin</button>
// <button onClick={() => onMakeSuperAdminClick(user.email)}>Make super admin</button>
