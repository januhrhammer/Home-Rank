import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";

import { t } from "../../lib/i18n";
import { type Search, searchesQuery } from "./novelty";
import styles from "./NoveltyListPage.module.css";

/** The user's novelty searches, newest first. They are started from a board ("Find tries"). */
export function NoveltyListPage() {
  const searches = useQuery(searchesQuery);
  return (
    <div className={styles.page}>
      <h1>{t("novelty.title")}</h1>
      <p className={styles.intro}>{t("novelty.intro")}</p>
      {searches.isError && <p role="alert">{t("novelty.loadFailed")}</p>}
      {searches.data?.items.length === 0 && <p className={styles.none}>{t("novelty.none")}</p>}
      <ul className={styles.list}>
        {searches.data?.items.map((search) => (
          <li key={search.id} className={styles.item}>
            <Link className={styles.name} to={`/novelty/${String(search.id)}`}>
              {search.start_label || t("novelty.unnamed")}
            </Link>
            <span className={styles.details}>{details(search)}</span>
            <span className={styles.status}>
              {t(`novelty.status.${search.status}`, { moves: search.own_moves })}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** "For White · against FIDE 1800 (Maia 1962)". */
export function details(search: Search): string {
  return [
    t(`novelty.for.${search.side}`),
    t("novelty.against", {
      rating: `${search.rating_kind === "lichess" ? "Lichess" : search.rating_kind.toUpperCase()} ${String(search.rating)}`,
      elo: String(search.elo), // a rating: 1962, not 1,962
    }),
  ].join(" · ");
}
