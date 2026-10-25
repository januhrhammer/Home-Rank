import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { databasesQuery, type Source } from "./explorer";

const STORAGE_KEY = "home-rank.explorer-source";

/**
 * Where the explorer and the position search take their games from, the same everywhere: the
 * user's own games, or the reference database chosen last. The choice is kept in the browser
 * (localStorage), like the notation. A database since deleted, or not ready, means the user's
 * own games again.
 */
export function useExplorerSource(): [Source, (source: Source) => void] {
  const [stored, setStored] = useState(storedSource);
  const databases = useQuery(databasesQuery);
  const change = (next: Source) => {
    setStored(next);
    try {
      localStorage.setItem(STORAGE_KEY, next.kind === "mine" ? "mine" : String(next.databaseId));
    } catch {
      // Storage can be blocked (private windows, strict settings): then it lasts this visit.
    }
  };
  const usable =
    stored.kind === "mine" ||
    (databases.data ?? []).some((d) => d.id === stored.databaseId && d.status === "ready");
  return [usable ? stored : { kind: "mine" }, change];
}

function storedSource(): Source {
  try {
    const id = Number(localStorage.getItem(STORAGE_KEY));
    return id > 0 ? { kind: "reference", databaseId: id } : { kind: "mine" };
  } catch {
    return { kind: "mine" };
  }
}
