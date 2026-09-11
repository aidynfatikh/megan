export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <span className={`wordmark ${compact ? "compact" : ""}`}>
      <svg
        viewBox="0 0 32 32"
        width="30"
        height="30"
        fill="none"
        aria-hidden="true"
      >
        <path
          d="M4 24V12c0-7 12-7 12 0v12M16 24V12c0-7 12-7 12 0v12"
          stroke="currentColor"
          strokeWidth="3.5"
          strokeLinecap="round"
        />
        <path
          d="M10 21v6m12-6v6"
          stroke="currentColor"
          strokeWidth="3.5"
          strokeLinecap="round"
        />
      </svg>
      {!compact && (
        <span>
          megan<span className="wordmark-dot">.</span>
        </span>
      )}
    </span>
  );
}
