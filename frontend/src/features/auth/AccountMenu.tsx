import { Button } from "react-aria-components";
import { Link, useLocation } from "react-router";

import { t } from "../../lib/i18n";
import styles from "./AccountMenu.module.css";
import { useCurrentUser } from "./currentUser";
import { useLogout } from "./logout";

/** The header's account area: who is logged in and a way out, or a way in. */
export function AccountMenu() {
  const { data: user } = useCurrentUser();
  const logout = useLogout();
  const { pathname } = useLocation();

  if (user === undefined) {
    return null; // not known yet
  }
  if (user === null && pathname === "/login") {
    return null; // the page itself is the way in
  }
  if (user === null) {
    return <Link to="/login">{t("header.logIn")}</Link>;
  }
  return (
    <div className={styles.account}>
      <span>{user.username}</span>
      <Button
        className={styles.logout}
        isPending={logout.isPending}
        onPress={() => {
          logout.mutate();
        }}
      >
        {t("header.logOut")}
      </Button>
    </div>
  );
}
