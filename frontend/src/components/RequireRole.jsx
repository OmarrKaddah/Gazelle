import React from 'react';
import { hasRole } from '../lib/roles';

// Renders children only if the user has `role`, else an access panel.
// App-level routing already gates this, but the wrapper is a backstop.

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
