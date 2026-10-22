import { Link, Outlet } from "react-router";

import { AccountMenu } from "../features/auth";
import { t } from "../lib/i18n";
import { SOURCE_CODE_URL } from "./config";
import styles from "./Layout.module.css";

/** The frame around every page: header, the page itself, footer. */
export function Layout() {
  return (
    <div className={styles.layout}>
      <header className={styles.header}>
        <Link to="/" className={styles.brand}>
          {t("app.name")}
        </Link>
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
