import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router";

import { ApiError } from "../../api/errors";
import { t } from "../../lib/i18n";
import { useUrlParams } from "../../lib/useUrlParams";
import { LinesPanel } from "./LinesPanel";
import { linesQuery, movesQuery, repertoireQuery } from "./repertoire";
import { DeleteDialog, ImportDialog, RenameDialog, SeedDialog } from "./RepertoireDialogs";
import { RepertoireEditor } from "./RepertoireEditor";
import styles from "./RepertoirePage.module.css";

/** One repertoire: its name and actions, its lines, and the editor for the line shown
 * (?line=…, else the first). */
export function RepertoirePage() {
  const repertoireId = Number(useParams().repertoireId);
  const repertoire = useQuery(repertoireQuery(repertoireId));
  const moves = useQuery(movesQuery(repertoireId));
  const lines = useQuery(linesQuery(repertoireId));
  const { params, setParam } = useUrlParams();

  if (repertoire.isError || moves.isError || lines.isError) {
    const error = repertoire.error ?? moves.error ?? lines.error;
    const notFound = error instanceof ApiError && error.status === 404;
    return <p role="alert">{t(notFound ? "repertoire.notFound" : "repertoire.loadFailed")}</p>;
  }
  const line =
    lines.data?.find((each) => String(each.id) === params.get("line")) ?? lines.data?.[0];
  if (!repertoire.data || !moves.data || !lines.data || !line) {
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
          <ImportDialog repertoire={repertoire.data} line={line} />
          <SeedDialog repertoire={repertoire.data} line={line} />
          <RenameDialog repertoire={repertoire.data} />
          <DeleteDialog repertoire={repertoire.data} />
        </div>
      </header>
      <LinesPanel
        repertoire={repertoire.data}
        lines={lines.data}
        moves={moves.data}
        current={line}
        onSelect={(lineId) => {
          setParam("line", lineId === null ? null : String(lineId));
        }}
      />
      <RepertoireEditor
        repertoire={repertoire.data}
        line={line}
        lines={lines.data}
        moves={moves.data}
      />
    </>
  );
}
