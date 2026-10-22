import { t } from "../../lib/i18n";

export function HomePage() {
  return (
    <>
      <h1>{t("app.name")}</h1>
      <p>{t("app.tagline")}</p>
    </>
  );
}
