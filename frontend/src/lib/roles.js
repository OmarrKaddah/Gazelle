// Roles come from the server (src/auth.py) on user.role. Route checks
// through these helpers so they stay in one place.

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

// Where a user lands after logging in.
export function defaultAreaForUser(user) {
  return isAdmin(user) ? 'admin' : 'main';
}
