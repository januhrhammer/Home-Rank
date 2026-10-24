import { useEffect } from "react";

/**
 * Keys for the whole page, e.g. arrows that step through a game. Not while typing in a field,
 * e.g. a tag's name, or choosing with radio buttons, and not in combination with Alt, Ctrl or
 * Cmd, which stay the browser's.
 */
export function useKeyboard(actions: Record<string, () => void>) {
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      // Typing goes to text fields; radio buttons use the arrow keys themselves. A checkbox or
      // switch (an input too) has no use for these keys, so they still work there.
      const typing =
        event.target instanceof Element &&
        event.target.closest("textarea, input:not([type=checkbox])");
      const action = actions[event.key];
      if (action === undefined || typing || event.altKey || event.ctrlKey || event.metaKey) {
        return;
      }
      event.preventDefault();
      action();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
    };
  });
}
