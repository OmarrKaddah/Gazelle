import React from 'react';
import { hasRole } from '../lib/roles';

// Route-protection wrapper. Renders its children only when the current user
// holds `role`; otherwise shows a clean "not authorized" panel. This is a
// defense-in-depth guard — the App-level routing already keeps non-admins out
// of the Admin area, but wrapping the page means it can never render for the
// wrong role even if routing changes later.

export default function RequireRole({ user, role, children }) {
  if (hasRole(user, role)) return children;

  return (
    <div className="flex h-full items-center justify-center bg-cream px-4">
      <div className="w-full max-w-sm text-center bg-cream-soft border border-cream-border rounded-2xl shadow-lg p-8">
        <div className="font-serif text-[22px] text-brand tracking-tight mb-1.5">
          Access restricted
        </div>
        <p className="text-[13px] text-ink-muted leading-relaxed">
          This area is available to {role} users only. Your account does not have
          the required permissions.
        </p>
      </div>
    </div>
  );
}
