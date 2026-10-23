import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Button, Dialog, Heading } from "react-aria-components";
import { Link, useParams } from "react-router";

import { ApiError } from "../../api/errors";
import { Board } from "../../components/Board";
import { dialogStyles as dialogs, ModalDialog } from "../../components/Dialog";
import { t } from "../../lib/i18n";
import { useNotation, withFigurines } from "../games";
import { MoveForm } from "../repertoire";
import { boardMove, legalDests, squaresOf } from "../training";
import { errorMessage } from "./errors";
import { clockText, outcomeFor, playedMoves } from "./moves";
import { type BotGame, gameQuery, usePlayMove, useResign, useSaveGame, useTakeBack } from "./play";
import styles from "./PlayPage.module.css";
import { StartGameDialog } from "./StartGameDialog";

/** A game against a bot: the board, the clocks, the moves, and what can be done. */
export function PlayPage() {
  const gameId = Number(useParams().gameId);
  const game = useQuery(gameQuery(gameId));

  if (game.isError) {
    const notFound = game.error instanceof ApiError && game.error.status === 404;
    return <p role="alert">{t(notFound ? "play.notFound" : "play.loadFailed")}</p>;
  }
  if (!game.data) {
    return null;
  }
  return (
    <Game game={game.data} receivedAt={game.dataUpdatedAt} onFlag={() => void game.refetch()} />
  );
}

interface GameProps {
  game: BotGame;
  /** When the game's state arrived (ms since 1970), for the running clock. */
  receivedAt: number;
  /** The user's time ran out: ask the server, which then ends the game. */
  onFlag: () => void;
}

function Game({ game, receivedAt, onFlag }: GameProps) {
  const [notation] = useNotation();
  const play = usePlayMove(game.id);
  const takeBack = useTakeBack(game.id);
  // The user's move, shown at once while the server answers with the bot's.
  const [pending, setPending] = useState<{ fen: string; uci: string } | null>(null);

  const moves = playedMoves(game.start_fen, game.moves);
  const playing = game.status === "playing";
  const usersTurn = playing && (game.fen.split(" ")[1] === "w") === (game.user_color === "white");
  const canMove = usersTurn && !play.isPending && !takeBack.isPending;
  const shown = pending ?? { fen: game.fen, uci: game.moves.at(-1) ?? "" };

  const move = (uci: string) => {
    const after = playedMoves(game.fen, [uci])[0];
    if (after === undefined) {
      return;
    }
    setPending({ fen: after.fen, uci });
    play.mutate(uci, {
      onSettled: () => {
        setPending(null);
      },
    });
  };

  const format = (san: string) => (notation === "figurines" ? withFigurines(san) : san);
  const botColor = game.user_color === "white" ? "black" : "white";

  return (
    <>
      <header className={styles.header}>
        <p className={styles.back}>
          <Link to="/play">{t("play.back")}</Link>
        </p>
        <h1 className={styles.title}>
          {t("play.vs", { you: t("play.you"), bot: game.opponent_name })}
        </h1>
        {game.start_label && <p className={styles.details}>{game.start_label}</p>}
      </header>
      <div className={styles.layout}>
        <div className={styles.boardColumn}>
          <ClockLine
            game={game}
            color={botColor}
            name={game.opponent_name}
            receivedAt={receivedAt}
          />
          <Board
            fen={shown.fen}
            orientation={game.user_color}
            lastMove={squaresOf(shown.uci)}
            label={t("play.board")}
            movable={
              canMove
                ? {
                    color: game.user_color,
                    dests: legalDests(game.fen),
                    onMove: (from, to) => {
                      move(boardMove(game.fen, from, to, ""));
                    },
                  }
                : undefined
            }
          />
          <ClockLine
            game={game}
            color={game.user_color}
            name={t("play.you")}
            receivedAt={receivedAt}
            onFlag={onFlag}
          />
        </div>
        <div className={styles.panel}>
          <p role="status" className={styles.status}>
            {statusText(game, play.isPending)}
          </p>
          {(play.error ?? takeBack.error) && (
            <p className={styles.error} role="alert">
              {errorMessage(play.error ?? takeBack.error ?? new Error())}
            </p>
          )}
          {canMove && <MoveForm label={t("play.typeMove")} fen={game.fen} onMove={move} />}
          <h2 className={styles.heading}>{t("play.moves")}</h2>
          {moves.length === 0 ? (
            <p className={styles.muted}>{t("play.noMoves")}</p>
          ) : (
            <ol className={styles.moves} aria-label={t("play.moves")}>
              {moves.map((played, index) => (
                <li
                  key={`${String(played.number)}${played.white ? "w" : "b"}`} // one per ply
                  className={styles.move}
                  aria-current={index === moves.length - 1 ? "step" : undefined}
                >
                  {(played.white || index === 0) && (
                    <span className={styles.number}>
                      {played.number}
                      {played.white ? "." : "…"}
                    </span>
                  )}
                  <span aria-label={played.san}>{format(played.san)}</span>
                </li>
              ))}
            </ol>
          )}
          <div className={styles.buttons}>
            {playing && game.clock === null && (
              <Button
                className={styles.secondary}
                isDisabled={!canMove || !hasUserMove(game)}
                isPending={takeBack.isPending}
                onPress={() => {
                  takeBack.mutate(undefined);
                }}
              >
                {t("play.takeBack")}
              </Button>
            )}
            {playing && <ResignDialog gameId={game.id} />}
            {!playing && <SaveButton game={game} />}
            {!playing && (
              <StartGameDialog
                startFen={game.start_fen}
                startLabel={game.start_label}
                side={game.user_color}
                triggerLabel={t("play.again")}
                triggerClassName={styles.secondary}
              />
            )}
          </div>
        </div>
      </div>
    </>
  );
}

/** Whether the user has a move to take back: the bot's first move doesn't count. */
function hasUserMove(game: BotGame): boolean {
  const firstIsWhite = game.start_fen.split(" ")[1] === "w";
  const userFirst = firstIsWhite === (game.user_color === "white");
  return game.moves.length >= (userFirst ? 2 : 3);
}

function statusText(game: BotGame, botThinking: boolean): string {
  const outcome = outcomeFor(game.result, game.user_color);
  if (outcome !== null && game.termination !== null) {
    return `${t(`play.outcome.${outcome}`)} ${t(`play.termination.${game.termination}`)}.`;
  }
  return botThinking ? t("play.thinking", { name: game.opponent_name }) : t("play.yourMove");
}

interface ClockLineProps {
  game: BotGame;
  color: "white" | "black";
  name: string;
  receivedAt: number;
  onFlag?: () => void;
}

/** A player's name and, in a timed game, their clock, running while they are to move. */
function ClockLine({ game, color, name, receivedAt, onFlag }: ClockLineProps) {
  const toMove = game.status === "playing" && game.fen.split(" ")[1] === color[0];
  const left =
    game.clock === null ? null : color === "white" ? game.clock.white_ms : game.clock.black_ms;
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (left === null || !toMove) {
      return undefined;
    }
    const timer = window.setInterval(() => {
      setNow(Date.now());
    }, 100);
    return () => {
      window.clearInterval(timer);
    };
  }, [left, toMove]);

  const shownMs = left === null ? null : toMove ? left - Math.max(0, now - receivedAt) : left;
  const flagged = shownMs !== null && shownMs <= 0 && toMove;
  useEffect(() => {
    if (flagged) {
      onFlag?.();
    }
  }, [flagged, onFlag]);

  return (
    <div className={styles.clockLine} data-to-move={toMove || undefined}>
      <span className={styles.player}>{name}</span>
      {shownMs !== null && (
        <span
          className={styles.clock}
          role="timer"
          aria-label={onFlag ? t("play.yourClock") : t("play.clockOf", { name })}
          data-low={shownMs < 20_000 || undefined}
        >
          {clockText(shownMs)}
        </span>
      )}
    </div>
  );
}

function ResignDialog({ gameId }: { gameId: number }) {
  const resign = useResign(gameId);
  return (
    <ModalDialog trigger={<Button className={styles.secondary}>{t("play.resign")}</Button>}>
      <Dialog className={dialogs.dialog} role="alertdialog">
        {({ close }) => (
          <div className={dialogs.form}>
            <Heading slot="title" className={dialogs.title}>
              {t("play.resignTitle")}
            </Heading>
            <p className={dialogs.note}>{t("play.resignText")}</p>
            {resign.error && (
              <p className={dialogs.error} role="alert">
                {errorMessage(resign.error)}
              </p>
            )}
            <div className={dialogs.buttons}>
              <Button className={dialogs.secondary} onPress={close}>
                {t("play.cancel")}
              </Button>
              <Button
                className={dialogs.danger}
                isPending={resign.isPending}
                onPress={() => {
                  resign.mutate(undefined, { onSuccess: close });
                }}
              >
                {t("play.resign")}
              </Button>
            </div>
          </div>
        )}
      </Dialog>
    </ModalDialog>
  );
}

function SaveButton({ game }: { game: BotGame }) {
  const save = useSaveGame(game.id);
  const savedId = game.saved_game_id ?? save.data?.game_id;
  if (savedId !== undefined) {
    return (
      <Link className={styles.link} to={`/games/${String(savedId)}`}>
        {t("play.openSaved")}
      </Link>
    );
  }
  return (
    <>
      <Button
        className={styles.primary}
        isPending={save.isPending}
        onPress={() => {
          save.mutate();
        }}
      >
        {t("play.save")}
      </Button>
      {save.error && (
        <p className={styles.error} role="alert">
          {errorMessage(save.error)}
        </p>
      )}
    </>
  );
}
