import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router";

import { ApiError } from "../../api/errors";
import { t } from "../../lib/i18n";
import { movesQuery, repertoireQuery } from "./repertoire";
import { DeleteDialog, ImportDialog, RenameDialog, SeedDialog } from "./RepertoireDialogs";
import { RepertoireEditor } from "./RepertoireEditor";
import styles from "./RepertoirePage.module.css";

/** One repertoire: its name and actions, and the editor. */
export function RepertoirePage() {
  const repertoireId = Number(useParams().repertoireId);
  const repertoire = useQuery(repertoireQuery(repertoireId));
  const moves = useQuery(movesQuery(repertoireId));

  if (repertoire.isError || moves.isError) {
    const error = repertoire.error ?? moves.error;
    const notFound = error instanceof ApiError && error.status === 404;
    return <p role="alert">{t(notFound ? "repertoire.notFound" : "repertoire.loadFailed")}</p>;
  }
  if (!repertoire.data || !moves.data) {
    return null;
  }
  return (
    <>
      <header className={styles.header}>
        <p className={styles.back}>
          <Link to="/repertoires">{t("repertoire.all")}</Link>
        </p>
        <h1 className={styles.title}>{repertoire.data.name}</h1>
        <p className={styles.details}>
          {t(`repertoire.for.${repertoire.data.color}`)} ·{" "}
          {t("repertoire.moveCount", { count: repertoire.data.move_count })}
          {repertoire.data.due > 0 && ` · ${t("repertoire.due", { count: repertoire.data.due })}`}
        </p>
        <div className={styles.actions}>
          <Link className={styles.primary} to={`/repertoires/${String(repertoireId)}/drill`}>
            {t("repertoire.drill")}
          </Link>
          <Link className={styles.action} to={`/repertoires/${String(repertoireId)}/gaps`}>
            {t("repertoire.gaps")}
          </Link>
          <ImportDialog repertoire={repertoire.data} />
          <SeedDialog repertoire={repertoire.data} />
          <RenameDialog repertoire={repertoire.data} />
          <DeleteDialog repertoire={repertoire.data} />
        </div>
      </header>
      <RepertoireEditor repertoire={repertoire.data} moves={moves.data} />
    </>
  );
}
