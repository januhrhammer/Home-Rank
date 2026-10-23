import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Button } from "react-aria-components";
import { Link, useParams } from "react-router";

import { ApiError } from "../../api/errors";
import { Board } from "../../components/Board";
import { t } from "../../lib/i18n";
import { type MoveNode, useNotation, withFigurines } from "../games";
import { squaresOf } from "../training";
import { fenAfter, type Gap, gapsQuery } from "./drill";
import { MoveText } from "./DrillQuestion";
import { errorMessage } from "./errors";
import styles from "./GapsPage.module.css";
import { movesQuery, type Repertoire, repertoireQuery, useAddMove } from "./repertoire";
import { buildRepertoireTree, lineTo } from "./tree";

/** The repertoire's gaps: where the user's games left it, most frequent first. */
export function GapsPage() {
  const repertoireId = Number(useParams().repertoireId);
  const repertoire = useQuery(repertoireQuery(repertoireId));

  if (repertoire.isError) {
    const notFound = repertoire.error instanceof ApiError && repertoire.error.status === 404;
    return <p role="alert">{t(notFound ? "repertoire.notFound" : "repertoire.loadFailed")}</p>;
  }
  if (!repertoire.data) {
    return null;
  }
  return (
    <>
      <header className={styles.header}>
        <p className={styles.back}>
          <Link to={`/repertoires/${String(repertoireId)}`}>
            {t("drill.backTo", { name: repertoire.data.name })}
          </Link>
        </p>
        <h1 className={styles.title}>{t("gaps.title", { name: repertoire.data.name })}</h1>
        <p className={styles.intro}>{t(`gaps.intro.${repertoire.data.color}`)}</p>
      </header>
      <GapList repertoire={repertoire.data} />
    </>
  );
}

/** A position's name without its move counters: the same position, however it was reached. */
function positionKey(fen: string): string {
  return fen.split(" ").slice(0, 4).join(" ");
}

function GapList({ repertoire }: { repertoire: Repertoire }) {
  const gaps = useQuery(gapsQuery(repertoire.id));
  const moves = useQuery(movesQuery(repertoire.id));
  const [notation] = useNotation();
  const figurines = notation === "figurines";
  const [selected, setSelected] = useState(0);
  const addMove = useAddMove(repertoire.id);

  // Where the repertoire reaches each position, to say after which moves a gap comes.
  const reachedAt = useMemo(() => {
    const tree = buildRepertoireTree(moves.data ?? []);
    const byPosition = new Map<string, MoveNode>();
    for (const node of tree.byId.values()) {
      if (!byPosition.has(positionKey(node.fen))) {
        byPosition.set(positionKey(node.fen), node);
      }
    }
    return byPosition;
  }, [moves.data]);

  if (gaps.isError) {
    return <p role="alert">{t("gaps.loadFailed")}</p>;
  }
  if (!gaps.data) {
    return null;
  }
  if (gaps.data.length === 0) {
    return <p className={styles.empty}>{t("gaps.none")}</p>;
  }
  const shown = gaps.data[Math.min(selected, gaps.data.length - 1)];
  const where = (gap: Gap) => {
    const node = reachedAt.get(positionKey(gap.fen));
    return node
      ? t("gaps.after", { line: lineTo(node, figurines ? withFigurines : undefined) })
      : t("gaps.atStart");
  };

  return (
    <div className={styles.gaps}>
      {shown && (
        <div className={styles.boardColumn}>
          <Board
            fen={fenAfter(shown.fen, shown.move_uci)}
            orientation={repertoire.color}
            lastMove={squaresOf(shown.move_uci)}
            label={t("gaps.board", { move: shown.move_san })}
          />
        </div>
      )}
      <div className={styles.listColumn}>
        {addMove.error && (
          <p className={styles.error} role="alert">
            {errorMessage(addMove.error)}
          </p>
        )}
        <ol className={styles.list}>
          {gaps.data.map((gap, i) => (
            <li
              key={`${gap.fen} ${gap.move_uci}`}
              className={styles.gap}
              aria-current={gap === shown || undefined}
            >
              <Button
                className={styles.show}
                onPress={() => {
                  setSelected(i);
                }}
              >
                <span className={styles.where}>{where(gap)}</span>{" "}
                <MoveText san={gap.move_san} figurines={figurines} />
              </Button>
              <p className={styles.details}>
                <span className={styles.kind} data-by-user={gap.by_user || undefined}>
                  {t(gap.by_user ? "gaps.byUser" : "gaps.notCovered")}
                </span>
                {" · "}
                {t("gaps.games", { count: gap.games })}
                {gap.last_played && ` · ${t("gaps.last", { date: gap.last_played })}`}
              </p>
              <div className={styles.actions}>
                <Button
                  className={styles.action}
                  isPending={addMove.isPending && addMove.variables.move_uci === gap.move_uci}
                  onPress={() => {
                    addMove.mutate({ fen: gap.fen, move_uci: gap.move_uci });
                  }}
                >
                  {t(gap.by_user ? "gaps.addMine" : "gaps.addReply")}
                </Button>
                {gap.game_ids[0] !== undefined && (
                  <Link className={styles.action} to={`/games/${String(gap.game_ids[0])}`}>
                    {t("gaps.latestGame")}
                  </Link>
                )}
              </div>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
