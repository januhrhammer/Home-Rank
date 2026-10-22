import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Button } from "react-aria-components";
import { useParams } from "react-router";

import { ApiError } from "../../api/errors";
import { Board } from "../../components/Board";
import { t } from "../../lib/i18n";
import styles from "./GamePage.module.css";
import { type Game, gameQuery } from "./games";
import { formatGameDate } from "./GameTable";
import { MoveList } from "./MoveList";
import { buildMoveTree, endOfLine, type MoveNode, moveNumber, type MoveTree } from "./moveTree";

export function GamePage() {
  const gameId = Number(useParams().gameId);
  const game = useQuery(gameQuery(gameId));

  if (game.isPending) {
    return null;
  }
  if (game.isError) {
    const notFound = game.error instanceof ApiError && game.error.status === 404;
    return <p role="alert">{t(notFound ? "viewer.notFound" : "viewer.loadFailed")}</p>;
  }
  return <GameViewer game={game.data} />;
}

function GameViewer({ game }: { game: Game }) {
  const tree = useMemo(() => buildMoveTree(game.pgn), [game.pgn]);
  if (tree === null) {
    return (
      <>
        <GameHeader game={game} />
        <p role="alert">{t("viewer.unreadable")}</p>
        <pre className={styles.pgn}>{game.pgn}</pre>
      </>
    );
  }
  return <Viewer game={game} tree={tree} />;
}

function Viewer({ game, tree }: { game: Game; tree: MoveTree }) {
  // The move whose position is shown; null is the starting position.
  const [current, setCurrent] = useState<MoveNode | null>(null);
  // The user's side is at the bottom unless they flip the board.
  const [flipped, setFlipped] = useState(false);
  const orientation = (game.user_color === "black") !== flipped ? "black" : "white";

  const go = {
    start: () => {
      setCurrent(null);
    },
    back: () => {
      setCurrent((move) => move?.parent ?? null);
    },
    forward: () => {
      setCurrent((move) => (move ? (move.children[0] ?? move) : (tree.firstMoves[0] ?? null)));
    },
    end: () => {
      setCurrent((move) => endOfLine(tree, move));
    },
  };

  useKeyboard({
    ArrowLeft: go.back,
    ArrowRight: go.forward,
    Home: go.start,
    End: go.end,
    f: () => {
      setFlipped((value) => !value);
    },
  });

  const label = current
    ? t("viewer.positionAfter", { move: `${moveNumber(current)} ${current.san}` })
    : t("viewer.startingPosition");

  return (
    <>
      <GameHeader game={game} />
      <div className={styles.viewer}>
        <div className={styles.boardColumn}>
          <Board
            fen={current?.fen ?? tree.startFen}
            orientation={orientation}
            lastMove={current?.squares}
            label={label}
          />
          <div className={styles.controls}>
            <Button className={styles.control} aria-label={t("viewer.start")} onPress={go.start}>
              ⏮
            </Button>
            <Button className={styles.control} aria-label={t("viewer.back")} onPress={go.back}>
              ◀
            </Button>
            <Button
              className={styles.control}
              aria-label={t("viewer.forward")}
              onPress={go.forward}
            >
              ▶
            </Button>
            <Button className={styles.control} aria-label={t("viewer.end")} onPress={go.end}>
              ⏭
            </Button>
            <Button
              className={styles.control}
              aria-label={t("viewer.flip")}
              onPress={() => {
                setFlipped((value) => !value);
              }}
            >
              ⇅
            </Button>
          </div>
          <p className={styles.hint}>{t("viewer.keys")}</p>
        </div>
        <div className={styles.sideColumn}>
          <MoveList tree={tree} current={current} onSelect={setCurrent} />
          <Actions game={game} fen={current?.fen ?? tree.startFen} />
        </div>
      </div>
    </>
  );
}

function GameHeader({ game }: { game: Game }) {
  const player = (name: string, elo: number | null) =>
    `${name || t("games.unknownPlayer")}${elo === null ? "" : ` (${String(elo)})`}`;
  const details = [
    game.event,
    formatGameDate(game.date_pgn),
    game.result === "1/2-1/2" ? "½-½" : game.result,
    [game.eco, game.opening].filter(Boolean).join(" "),
    game.time_control,
  ].filter(Boolean);

  return (
    <header className={styles.header}>
      <h1 className={styles.title}>
        {player(game.white, game.white_elo)} – {player(game.black, game.black_elo)}
      </h1>
      <p className={styles.details}>{details.join(" · ")}</p>
      {[...game.tags, ...game.collections].length > 0 && (
        <p className={styles.labels}>
          {[...game.collections, ...game.tags].map((label) => (
            <span key={`${String(label.id)}-${label.name}`} className={styles.label}>
              {label.name}
            </span>
          ))}
        </p>
      )}
    </header>
  );
}

function Actions({ game, fen }: { game: Game; fen: string }) {
  const [copied, setCopied] = useState<string | null>(null);

  const copy = (text: string, what: string) => {
    void navigator.clipboard.writeText(text).then(() => {
      setCopied(what);
    });
  };

  return (
    <div className={styles.actions}>
      <Button
        className={styles.action}
        onPress={() => {
          copy(fen, t("viewer.copiedFen"));
        }}
      >
        {t("viewer.copyFen")}
      </Button>
      <Button
        className={styles.action}
        onPress={() => {
          copy(game.pgn, t("viewer.copiedPgn"));
        }}
      >
        {t("viewer.copyPgn")}
      </Button>
      <a className={styles.action} href={`/api/v1/games/${String(game.id)}/pgn`} download>
        {t("viewer.download")}
      </a>
      {/* Announced by screen readers without moving the focus. */}
      <span role="status" className={styles.copied}>
        {copied}
      </span>
    </div>
  );
}

/** Keys that step through the game. Combinations with Alt, Ctrl or Cmd stay the browser's. */
function useKeyboard(actions: Record<string, () => void>) {
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const action = actions[event.key];
      if (action === undefined || event.altKey || event.ctrlKey || event.metaKey) {
        return;
      }
      event.preventDefault();
      action();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
    };
  });
}
