import { useState } from "react";
import { RouterProvider } from "react-aria-components";
import { Link, NavLink, Outlet, useHref, useLocation, useNavigate } from "react-router";

import { MenuIcon } from "../components/Icons";
import { AccountMenu, useCurrentUser } from "../features/auth";
import { t } from "../lib/i18n";
import { SOURCE_CODE_URL } from "./config";
import styles from "./Layout.module.css";

/** The frame around every page: header, the page itself, footer. */
export function Layout() {
  const { data: user } = useCurrentUser();
  const navigate = useNavigate();
  // On narrow screens the pages and the account area hide behind a menu button. The menu is
  // open for the page it was opened on, so following one of its links closes it.
  const { pathname } = useLocation();
  const [menuOpenOn, setMenuOpenOn] = useState<string | null>(null);
  const menuOpen = menuOpenOn === pathname;

  return (
    // Lets React Aria's links, e.g. the rows of the game list, navigate within the app.
    <RouterProvider
      navigate={(path) => {
        void navigate(path);
      }}
      useHref={useHref}
    >
      <div className={styles.layout}>
        <header className={styles.header}>
          <Link to="/" className={styles.brand}>
            {t("app.name")}
          </Link>
          {user && (
            <button
              type="button"
              className={styles.menuButton}
              aria-expanded={menuOpen}
              aria-controls="site-menu"
              onClick={() => {
                setMenuOpenOn(menuOpen ? null : pathname);
              }}
            >
              <MenuIcon />
              {t("nav.menu")}
            </button>
          )}
          <div
            id="site-menu"
            className={styles.menu}
            data-collapsible={user ? true : undefined}
            data-open={menuOpen || undefined}
          >
            {user && (
              <nav className={styles.nav} aria-label={t("nav.label")}>
                {/* NavLink marks the link to the current page with aria-current="page". */}
                <NavLink to="/games" className={styles.navLink}>
                  {t("nav.games")}
                </NavLink>
                <NavLink to="/train" className={styles.navLink}>
                  {t("nav.train")}
                </NavLink>
                <NavLink to="/repertoires" className={styles.navLink}>
                  {t("nav.repertoire")}
                </NavLink>
                <NavLink to="/search" className={styles.navLink}>
                  {t("nav.search")}
                </NavLink>
                <NavLink to="/reference" className={styles.navLink}>
                  {t("nav.reference")}
                </NavLink>
                <NavLink to="/labels" className={styles.navLink}>
                  {t("nav.labels")}
                </NavLink>
                <NavLink to="/import" className={styles.navLink}>
                  {t("nav.import")}
                </NavLink>
              </nav>
            )}
            <AccountMenu />
          </div>
        </header>
        <main className={styles.main}>
          <Outlet />
        </main>
        <footer className={styles.footer}>
          <a href={SOURCE_CODE_URL}>{t("footer.sourceCode")}</a>
        </footer>
      </div>
    </RouterProvider>
  );
}
