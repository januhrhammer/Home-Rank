import { Link } from "react-router";

import { t } from "../lib/i18n";

export function NotFoundPage() {
  return (
    <>
      <h1>{t("notFound.title")}</h1>
      <Link to="/">{t("notFound.backHome")}</Link>
    </>
  );
}
