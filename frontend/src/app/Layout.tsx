import { Link, NavLink, Outlet } from "react-router";

import { AccountMenu, useCurrentUser } from "../features/auth";
import { t } from "../lib/i18n";
import { SOURCE_CODE_URL } from "./config";
import styles from "./Layout.module.css";

/** The frame around every page: header, the page itself, footer. */
export function Layout() {
  const { data: user } = useCurrentUser();

  return (
    <div className={styles.layout}>
      <header className={styles.header}>
        <Link to="/" className={styles.brand}>
          {t("app.name")}
        </Link>
        {user && (
          <nav className={styles.nav} aria-label={t("nav.label")}>
            {/* NavLink marks the link to the current page with aria-current="page". */}
            <NavLink to="/import" className={styles.navLink}>
              {t("nav.import")}
            </NavLink>
          </nav>
        )}
        <AccountMenu />
      </header>
      <main className={styles.main}>
        <Outlet />
      </main>
      <footer className={styles.footer}>
        <a href={SOURCE_CODE_URL}>{t("footer.sourceCode")}</a>
      </footer>
    </div>
  );
}
