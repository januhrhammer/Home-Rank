import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import {
  Button,
  Disclosure,
  DisclosurePanel,
  Heading,
  SwitchButton,
  SwitchField,
} from "react-aria-components";
import { Link, useParams } from "react-router";

import { ApiError } from "../../api/errors";
import { Board } from "../../components/Board";
import { BackIcon, EndIcon, FlipIcon, ForwardIcon, StartIcon } from "../../components/Icons";
import { t } from "../../lib/i18n";
import { useKeyboard } from "../../lib/useKeyboard";
import type { PositionEval } from "../analysis";
import { AnalysisPanel, EvalBar, EvalGraph, useGameAnalysis } from "../analysis";
import { arrowsOf, EnginePanel, useLiveAnalysis } from "../engine";
import { ExplorerPanel, type Source } from "../explorer";
import { FindTriesDialog, ucisOf } from "../novelty";
import { StartGameDialog } from "../play";
import { boardMove, legalDests, turnOf } from "../training";
import { addMoves, deleteVariation, setComment, toggleMark, variationStart } from "./annotate";
import { AnnotationTools } from "./AnnotationTools";
import styles from "./GamePage.module.css";
import { type Game, gameQuery, useAnnotate } from "./games";
import { formatGameDate } from "./GameTable";
import { LabelPicker } from "./LabelPicker";
import { MoveList, type WeakMove } from "./MoveList";
import {
  buildMoveTree,
  endOfLine,
  mainLine,
  type MoveNode,
  moveNumber,
  type MoveTree,
  nodeAtPath,
} from "./moveTree";
import { useNotation, withFigurines } from "./notation";

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
  const annotate = useAnnotate(game.id);
  // A change being saved is shown at once; if saving fails, the stored game is shown again.
  const pgn = annotate.isPending ? annotate.variables : game.pgn;
  const tree = useMemo(() => buildMoveTree(pgn), [pgn]);
  if (tree === null) {
    return (
      <>
        <GameHeader game={game} />
        <p role="alert">{t("viewer.unreadable")}</p>
        <pre className={styles.pgn}>{game.pgn}</pre>
      </>
    );
  }
  return <Viewer game={game} pgn={pgn} tree={tree} annotate={annotate} />;
}

interface ViewerProps {
  game: Game;
  /** The game's PGN as shown: the stored one, or a change being saved. */
  pgn: string;
  tree: MoveTree;
  annotate: ReturnType<typeof useAnnotate>;
}

function Viewer({ game, pgn, tree, annotate }: ViewerProps) {
  // The move whose position is shown, by its path, so it stays chosen when an annotation
  // rebuilds the tree; null is the starting position.
  const [currentPath, setCurrentPath] = useState<number[] | null>(null);
  const current = nodeAtPath(tree, currentPath);
  const setCurrent = (node: MoveNode | null) => {
    setCurrentPath(node?.path ?? null);
  };
  // In annotation mode the board takes moves (added as variations) and the tools show.
  const [annotating, setAnnotating] = useState(false);
  // The user's side is at the bottom unless they flip the board.
  const [flipped, setFlipped] = useState(false);
  const [notation, setNotation] = useNotation();
  const [explorerSource, setExplorerSource] = useState<Source>({ kind: "mine" });
  const orientation = (game.user_color === "black") !== flipped ? "black" : "white";
  const analysis = useGameAnalysis(game.id);
  const engine = useEngineView(tree, analysis.data?.positions ?? [], current);
  const formatMoves = (line: string) =>
    notation === "figurines" ? line.split(" ").map(withFigurines).join(" ") : line;

  const go = {
    start: () => {
      setCurrent(null);
    },
    back: () => {
      setCurrent(current?.parent ?? null);
    },
    forward: () => {
      setCurrent(current ? (current.children[0] ?? current) : (tree.firstMoves[0] ?? null));
    },
    end: () => {
      setCurrent(endOfLine(tree, current));
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

  const shownFen = current?.fen ?? tree.startFen;
  const live = useLiveAnalysis(shownFen);

  // Each annotation is saved at once; moves played go to the move they lead to.
  const path = current?.path ?? [];
  const playMoves = (moves: string[]) => {
    const added = addMoves(pgn, path, moves);
    annotate.mutate(added.pgn);
    setCurrentPath(added.path);
  };

  const label = current
    ? t("viewer.positionAfter", { move: `${moveNumber(current)} ${current.san}` })
    : t("viewer.startingPosition");

  return (
    <>
      <GameHeader game={game} />
      <div className={styles.viewer}>
        <div className={styles.boardColumn}>
          <div className={styles.boardRow}>
            {engine.analysed && <EvalBar position={engine.position} orientation={orientation} />}
            <Board
              fen={current?.fen ?? tree.startFen}
              orientation={orientation}
              lastMove={current?.squares}
              label={label}
              arrows={arrowsOf(live.lines)}
              movable={
                annotating && !annotate.isPending
                  ? {
                      color: turnOf(shownFen),
                      dests: legalDests(shownFen),
                      onMove: (from, to) => {
                        playMoves([boardMove(shownFen, from, to, "")]);
                      },
                    }
                  : undefined
              }
            />
          </div>
          <div className={styles.controls}>
            <Button className={styles.control} aria-label={t("viewer.start")} onPress={go.start}>
              <StartIcon />
            </Button>
            <Button className={styles.control} aria-label={t("viewer.back")} onPress={go.back}>
              <BackIcon />
            </Button>
            <Button
              className={styles.control}
              aria-label={t("viewer.forward")}
              onPress={go.forward}
            >
              <ForwardIcon />
            </Button>
            <Button className={styles.control} aria-label={t("viewer.end")} onPress={go.end}>
              <EndIcon />
            </Button>
            <Button
              className={styles.control}
              aria-label={t("viewer.flip")}
              onPress={() => {
                setFlipped((value) => !value);
              }}
            >
              <FlipIcon />
            </Button>
          </div>
          <EvalGraph
            positions={engine.positions}
            current={engine.index}
            onSelect={(index) => {
              setCurrent(engine.line[index - 1] ?? null);
            }}
          />
          <p className={styles.hint}>{t("viewer.keys")}</p>
        </div>
        <div className={styles.sideColumn}>
          <EnginePanel
            fen={shownFen}
            analysis={live}
            onAddLine={annotating ? playMoves : undefined}
          />
          <section className={styles.annotate} aria-label={t("annotate.title")}>
            <SwitchField isSelected={annotating} onChange={setAnnotating}>
              <SwitchButton className={styles.notation}>
                <span className={styles.track}>
                  <span className={styles.thumb} />
                </span>
                {t("annotate.title")}
              </SwitchButton>
            </SwitchField>
            {annotate.isError && (
              <p className={styles.error} role="alert">
                {t("annotate.failed")}
              </p>
            )}
            {annotating && (
              <AnnotationTools
                current={current}
                format={(san) => (notation === "figurines" ? withFigurines(san) : san)}
                isSaving={annotate.isPending}
                onComment={(text) => {
                  annotate.mutate(setComment(pgn, path, text));
                }}
                onMark={(nag) => {
                  annotate.mutate(toggleMark(pgn, path, nag));
                }}
                onDelete={() => {
                  annotate.mutate(deleteVariation(pgn, path));
                  // Back to the move the variation branched off from.
                  const start = variationStart(path);
                  setCurrentPath(start.length > 1 ? start.slice(0, -1) : null);
                }}
              />
            )}
          </section>
          <AnalysisPanel
            gameId={game.id}
            analysis={analysis.data}
            position={engine.position}
            fen={current?.fen ?? tree.startFen}
            formatMoves={formatMoves}
          />
          <MoveList
            tree={tree}
            current={current}
            onSelect={setCurrent}
            notation={notation}
            weakMoves={engine.weakMoves}
          />
          <Disclosure className={styles.explorer}>
            <Heading level={2} className={styles.explorerHeading}>
              <Button slot="trigger" className={styles.explorerButton}>
                <span className={styles.chevron} aria-hidden="true">
                  ▸
                </span>
                {t("explorer.title")}
              </Button>
            </Heading>
            <DisclosurePanel>
              <ExplorerPanel
                fen={current?.fen ?? tree.startFen}
                source={explorerSource}
                onSourceChange={setExplorerSource}
                formatMove={(san) => (notation === "figurines" ? withFigurines(san) : san)}
                onMove={(move) => {
                  // Step forward if the game (or one of its variations) goes on with the move.
                  const next = current ? current.children : tree.firstMoves;
                  const found = next.find((child) => child.san === move.san);
                  if (found) {
                    setCurrent(found);
                  }
                }}
              />
              <Link
                className={styles.searchLink}
                to={`/search?${new URLSearchParams({ fen: current?.fen ?? tree.startFen }).toString()}`}
              >
                {t("explorer.searchPosition")}
              </Link>
            </DisclosurePanel>
          </Disclosure>
          <SwitchField
            isSelected={notation === "figurines"}
            onChange={(on) => {
              setNotation(on ? "figurines" : "letters");
            }}
          >
            <SwitchButton className={styles.notation}>
              <span className={styles.track}>
                <span className={styles.thumb} />
              </span>
              {t("viewer.figurines")}
            </SwitchButton>
          </SwitchField>
          <LabelPicker kind="tags" gameId={game.id} labels={game.tags} />
          <LabelPicker kind="collections" gameId={game.id} labels={game.collections} />
          <Actions
            game={game}
            fen={current?.fen ?? tree.startFen}
            after={current ? `${moveNumber(current)} ${current.san}` : null}
            moves={ucisOf(tree.startFen, sansTo(current))}
          />
        </div>
      </div>
    </>
  );
}

/**
 * The engine's results lined up with the moves: the main line's evaluations (variations have
 * none), the shown position's, and the weak moves for the move list.
 */
function useEngineView(tree: MoveTree, positions: PositionEval[], current: MoveNode | null) {
  return useMemo(() => {
    const line = mainLine(tree);
    const byPly = new Map(positions.map((position) => [position.ply, position]));
    const weakMoves = new Map<number, WeakMove>();
    line.forEach((move, i) => {
      const moveClass = byPly.get(i + 1)?.move_class;
      if (moveClass && moveClass !== "good") {
        weakMoves.set(move.id, moveClass);
      }
    });
    // 0 for the starting position, n for the position after the n-th move of the main line.
    const index = current === null ? 0 : line.indexOf(current) + 1 || null;
    return {
      line,
      positions,
      weakMoves,
      index,
      position: index === null ? undefined : byPly.get(index),
      analysed: positions.length > 0,
    };
  }, [tree, positions, current]);
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
    </header>
  );
}

/** The moves (SAN) from the start to a node of the move tree, variations included. */
function sansTo(node: MoveNode | null): string[] {
  const sans: string[] = [];
  for (let at = node; at !== null; at = at.parent) {
    sans.unshift(at.san);
  }
  return sans;
}

interface ActionsProps {
  game: Game;
  /** The position shown. */
  fen: string;
  /** The moves (UCI) from the game's start to it. */
  moves: string[];
  /** The move that led there, e.g. "12. Nf3", to name a game played from it. */
  after: string | null;
}

function Actions({ game, fen, moves, after }: ActionsProps) {
  const [copied, setCopied] = useState<string | null>(null);
  const players = `${game.white || t("games.unknownPlayer")} – ${game.black || t("games.unknownPlayer")}`;

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
      <StartGameDialog
        startFen={fen}
        startLabel={
          after === null ? players : t("play.labelAfter", { start: players, line: after })
        }
        side={game.user_color || (fen.split(" ")[1] === "b" ? "black" : "white")}
        triggerLabel={t("play.newFrom")}
        triggerClassName={styles.action}
      />
      <FindTriesDialog
        fen={fen}
        moves={moves}
        label={after === null ? players : t("play.labelAfter", { start: players, line: after })}
        side={game.user_color || (fen.split(" ")[1] === "b" ? "black" : "white")}
        triggerClassName={styles.action}
      />
      {/* Announced by screen readers without moving the focus. */}
      <span role="status" className={styles.copied}>
        {copied}
      </span>
    </div>
  );
}
