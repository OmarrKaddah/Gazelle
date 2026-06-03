// Role-based access control — single source of truth for the frontend.
// Roles are assigned server-side (see src/auth.py) and arrive on the user
// object as `user.role`. Keep all role checks routed through these helpers so
// access rules stay centralized and easy to extend.

export const ROLES = {
  ADMIN: 'Admin',
  SENIOR_COMPLIANCE: 'Senior Compliance',
  COMPLIANCE_ANALYST: 'Compliance Analyst',
  EXTERNAL: 'External',
};

export function hasRole(user, role) {
  return Boolean(user) && user.role === role;
}

export function isAdmin(user) {
  return hasRole(user, ROLES.ADMIN);
}

// Where a user should land immediately after logging in.
export function defaultAreaForUser(user) {
  return isAdmin(user) ? 'admin' : 'main';
}
