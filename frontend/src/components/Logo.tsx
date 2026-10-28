export function Logo({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <circle cx="16" cy="16" r="10" fill="none" stroke="#e9eeea" strokeWidth="2" />
      <path d="M16 9l7 7-7 7-7-7z" fill="#b3126b" />
    </svg>
  );
}
