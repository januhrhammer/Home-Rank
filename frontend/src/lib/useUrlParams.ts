import { useCallback, useRef } from "react";
import { useSearchParams } from "react-router";

/**
 * The page address's query parameters, and a function to change one of them.
 *
 * React Router's setSearchParams builds on the parameters of the last render, so a second
 * change made before React has rendered again would overwrite the first, e.g. choosing a filter
 * and quickly clicking a column to sort. So each change is remembered with the parameters it was
 * based on; until the router renders newer parameters, the next change builds on it instead.
 */
export function useUrlParams() {
  const [params, setParams] = useSearchParams();
  const pendingRef = useRef<{ basedOn: URLSearchParams; result: URLSearchParams } | null>(null);

  /** Set a parameter; null removes it. `alsoRemove` names parameters to drop with it. */
  const setParam = useCallback(
    (name: string, value: string | null, alsoRemove: string[] = []) => {
      const latest = pendingRef.current?.basedOn === params ? pendingRef.current.result : params;
      const next = new URLSearchParams(latest);
      if (value === null) {
        next.delete(name);
      } else {
        next.set(name, value);
      }
      for (const other of alsoRemove) {
        next.delete(other);
      }
      pendingRef.current = { basedOn: params, result: next };
      setParams(next);
    },
    [params, setParams],
  );

  return { params, setParam };
}
