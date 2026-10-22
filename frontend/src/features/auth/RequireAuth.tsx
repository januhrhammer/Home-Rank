import { Navigate, Outlet, useLocation } from "react-router";

import { t } from "../../lib/i18n";
import { useCurrentUser } from "./currentUser";

/**
 * Shows the pages inside it to logged-in users only. Everyone else goes to the login page,
 * which sends them back here afterwards (see returnAddress).
 */
export function RequireAuth() {
  const currentUser = useCurrentUser();
  const location = useLocation();

  if (currentUser.isPending) {
    return null; // still asking the server; the login page would otherwise flash up briefly
  }
  if (currentUser.isError) {
    return <p role="alert">{t("errors.loadFailed")}</p>;
  }
  if (currentUser.data === null) {
    const from = location.pathname + location.search;
    return <Navigate to="/login" replace state={{ from }} />;
  }
  return <Outlet />;
}

/** Where to go after logging in: the page RequireAuth sent the user away from, or the start. */
export function returnAddress(routerState: unknown): string {
  if (
    typeof routerState === "object" &&
    routerState !== null &&
    "from" in routerState &&
    typeof routerState.from === "string"
  ) {
    return routerState.from;
  }
  return "/";
}
