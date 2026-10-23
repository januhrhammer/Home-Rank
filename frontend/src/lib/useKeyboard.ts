import { useEffect } from "react";

/**
 * Keys for the whole page, e.g. arrows that step through a game. Not while typing in a field,
 * e.g. a tag's name, and not in combination with Alt, Ctrl or Cmd, which stay the browser's.
 */
export function useKeyboard(actions: Record<string, () => void>) {
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const typing = event.target instanceof Element && event.target.closest("input, textarea");
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
