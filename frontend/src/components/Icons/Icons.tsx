// Small icons for buttons, drawn in the text colour. The button names what it does (its
// aria-label), so the icons are hidden from screen readers.

function Icon({ path }: { path: string }) {
  return (
    <svg width="1.25em" height="1.25em" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d={path} fill="currentColor" />
    </svg>
  );
}

/** A bar and a triangle pointing left: to the start. */
export function StartIcon() {
  return <Icon path="M6 5h2v14H6zM19 5v14l-10-7z" />;
}

/** A triangle pointing left. */
export function BackIcon() {
  return <Icon path="M16 5v14L6 12z" />;
}

/** A triangle pointing right. */
export function ForwardIcon() {
  return <Icon path="M8 5v14l10-7z" />;
}

/** A triangle pointing right and a bar: to the end. */
export function EndIcon() {
  return <Icon path="M5 5v14l10-7zM16 5h2v14h-2z" />;
}

/** An arrow up and an arrow down: turn the board around. */
export function FlipIcon() {
  return <Icon path="M7 3l-4.5 5H6v9h2V8h3.5zM17 21l4.5-5H18V7h-2v9h-3.5z" />;
}

/** Three bars: a menu. */
export function MenuIcon() {
  return <Icon path="M3 6h18v2H3zM3 11h18v2H3zM3 16h18v2H3z" />;
}
