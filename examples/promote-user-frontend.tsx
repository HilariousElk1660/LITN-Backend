const BACKEND_BASE_URL = process.env.BACKEND_BASE_URL || "http://localhost:8000";

function normalizeRole(role: string) {
  const normalized = role.toLowerCase().replace(/[-\s]/g, "_");
  return normalized === "superadmin" ? "super_admin" : normalized;
}

export async function promoteUserToRole(email: string, role: string, token: string) {
  const normalizedRole = normalizeRole(role);
  const url = `${BACKEND_BASE_URL}/promote_user`;

  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${token}`,
      "Content-Type": "application/json",
      "Accept": "application/json",
    },
    body: JSON.stringify({
      email,
      role: normalizedRole,
    }),
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Promotion failed with status ${response.status}`);
  }

  return response.json();
}

export async function handlePromoteClick(email: string, role: string) {
  const token = window.localStorage.getItem("access_token");
  if (!token) {
    throw new Error("Missing auth token. Sign in as an admin first.");
  }

  return promoteUserToRole(email, role, token);
}

// If your current code does something like this, remove it entirely:
//
// await supabase
//   .from('user_roles')
//   .insert([{ user_id, role: 'super-admin' }], { onConflict: 'user_id,role' });
//
// instead, replace it with this backend call:
//
// import { handlePromoteClick } from "../examples/promote-user-frontend";
//
// const onMakeAdmin = async (email: string) => {
//   try {
//     const result = await handlePromoteClick(email, "admin");
//     console.log(result.message);
//   } catch (error) {
//     console.error(error);
//   }
// };
//
// const onMakeSuperAdmin = async (email: string) => {
//   try {
//     const result = await handlePromoteClick(email, "super-admin");
//     console.log(result.message);
//   } catch (error) {
//     console.error(error);
//   }
// };
