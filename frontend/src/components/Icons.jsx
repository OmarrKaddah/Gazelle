import React from 'react';

const baseProps = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.6,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  viewBox: '0 0 24 24',
};

export const PlusIcon = (p) => (
  <svg {...baseProps} {...p}>
    <path d="M12 5v14M5 12h14" />
  </svg>
);

export const MenuIcon = (p) => (
  <svg {...baseProps} {...p}>
    <path d="M4 6h16M4 12h16M4 18h16" />
  </svg>
);

export const PanelLeftIcon = (p) => (
  <svg {...baseProps} {...p}>
    <rect x="3" y="4" width="18" height="16" rx="2" />
    <path d="M9 4v16" />
  </svg>
);

export const ChatIcon = (p) => (
  <svg {...baseProps} {...p}>
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
  </svg>
);

export const GraphIcon = (p) => (
  <svg {...baseProps} {...p}>
    <circle cx="6" cy="6" r="2.5" />
    <circle cx="18" cy="6" r="2.5" />
    <circle cx="12" cy="18" r="2.5" />
    <path d="M7.5 7.5l3.5 8.5M16.5 7.5l-3.5 8.5M8 6h8" />
  </svg>
);

export const SettingsIcon = (p) => (
  <svg {...baseProps} {...p}>
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
  </svg>
);

export const TrashIcon = (p) => (
  <svg {...baseProps} {...p}>
    <path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
  </svg>
);

export const SendIcon = (p) => (
  <svg {...baseProps} {...p}>
    <path d="M22 2L11 13M22 2l-7 20-4-9-9-4z" />
  </svg>
);

export const ChevronDownIcon = (p) => (
  <svg {...baseProps} {...p}>
    <path d="M6 9l6 6 6-6" />
  </svg>
);

export const SearchIcon = (p) => (
  <svg {...baseProps} {...p}>
    <circle cx="11" cy="11" r="7" />
    <path d="M21 21l-4.35-4.35" />
  </svg>
);

export const RefreshIcon = (p) => (
  <svg {...baseProps} {...p}>
    <path d="M3 12a9 9 0 0 1 15.5-6.4L21 8" />
    <path d="M21 3v5h-5" />
    <path d="M21 12a9 9 0 0 1-15.5 6.4L3 16" />
    <path d="M3 21v-5h5" />
  </svg>
);

export const SlidersIcon = (p) => (
  <svg {...baseProps} {...p}>
    <path d="M4 6h12M16 6h4M4 12h4M8 12h12M4 18h14M18 18h2" />
    <circle cx="16" cy="6" r="2" />
    <circle cx="8" cy="12" r="2" />
    <circle cx="18" cy="18" r="2" />
  </svg>
);

export const XIcon = (p) => (
  <svg {...baseProps} {...p}>
    <path d="M18 6L6 18M6 6l12 12" />
  </svg>
);

export const UploadIcon = (p) => (
  <svg {...baseProps} {...p}>
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <path d="M12 16V4" />
    <path d="M7 9l5-5 5 5" />
  </svg>
);

export const FileIcon = (p) => (
  <svg {...baseProps} {...p}>
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <path d="M14 2v6h6" />
  </svg>
);

export const LogoMark = ({ className = '', ...p }) => (
  <div
    className={`overflow-hidden rounded-full bg-white ring-1 ring-cream-border flex items-center justify-center ${className}`}
    {...p}
  >
    <img
      src="/logo.jpeg"
      alt="Gazelle"
      className="w-full h-full object-cover scale-[1.35]"
      draggable={false}
    />
  </div>
);
