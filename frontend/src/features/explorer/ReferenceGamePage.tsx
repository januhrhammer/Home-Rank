import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Button } from "react-aria-components";
import { useNavigate, useParams } from "react-router";

import { Board } from "../../components/Board";
import { t } from "../../lib/i18n";
import {
  buildMoveTree,
  endOfLine,
  formatGameDate,
  MoveList,
  type MoveNode,
  useNotation,
} from "../games";
import { referenceGameQuery, useCopyGame } from "./explorer";
import styles from "./ReferencePage.module.css";

/** A reference game to replay, and copy into your own games. */
export function ReferenceGamePage() {
  const params = useParams();
  const databaseId = Number(params.databaseId);
  const gameId = Number(params.gameId);
  const game = useQuery(referenceGameQuery(databaseId, gameId));
  const tree = useMemo(() => (game.data ? buildMoveTree(game.data.pgn) : null), [game.data]);
  const [current, setCurrent] = useState<MoveNode | null>(null);
  const [notation] = useNotation();
  const copy = useCopyGame(databaseId, gameId);
  const navigate = useNavigate();

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (tree === null || event.altKey || event.ctrlKey || event.metaKey) {
        return;
      }
      if (event.key === "ArrowRight") {
        setCurrent((move) => (move ? (move.children[0] ?? move) : (tree.firstMoves[0] ?? null)));
      } else if (event.key === "ArrowLeft") {
        setCurrent((move) => move?.parent ?? null);
      } else if (event.key === "End") {
        setCurrent((move) => endOfLine(tree, move));
      } else if (event.key === "Home") {
        setCurrent(null);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [tree]);

  if (game.isError) {
    return <p role="alert">{t("viewer.notFound")}</p>;
  }
  if (!game.data || tree === null) {
    return null;
  }
  const data = game.data;
  return (
    <div>
      <h1 className={styles.title}>
        {data.white || "?"} – {data.black || "?"}
      </h1>
      <p className={styles.note}>
        {[
          data.event,
          formatGameDate(data.date_pgn),
          data.result === "1/2-1/2" ? "½-½" : data.result,
          [data.eco, data.opening].filter(Boolean).join(" "),
        ]
          .filter(Boolean)
          .join(" · ")}
      </p>
      <div className={styles.viewer}>
        <div className={styles.board}>
          <Board fen={current?.fen ?? tree.startFen} lastMove={current?.squares} />
          <p className={styles.note}>{t("viewer.keys")}</p>
        </div>
        <div className={styles.side}>
          <MoveList tree={tree} current={current} onSelect={setCurrent} notation={notation} />
          <Button
            className={styles.button}
            isPending={copy.isPending}
            onPress={() => {
              copy.mutate(undefined, {
                onSuccess: (copied) => {
                  void navigate(`/games/${String(copied.game_id)}`);
                },
              });
            }}
          >
            {t("reference.copy")}
          </Button>
          {copy.isError && <p role="alert">{t("reference.copyFailed")}</p>}
        </div>
      </div>
    </div>
  );
}
