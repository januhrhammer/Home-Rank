import { useQuery } from "@tanstack/react-query";
import type { SquareName } from "chessops";
import { useState } from "react";
import { Button, Dialog, Heading } from "react-aria-components";
import { Link, useNavigate, useParams } from "react-router";

import { ApiError } from "../../api/errors";
import { Board } from "../../components/Board";
import { dialogStyles as dialogs, ModalDialog } from "../../components/Dialog";
import { t } from "../../lib/i18n";
import { useNotation, withFigurines } from "../games";
import { playedMoves } from "../play";
import { squaresOf } from "../training";
import { errorMessage } from "./errors";
import { lineText, pawns, percent, tryMoves } from "./lines";
import {
  isActive,
  type NoveltyTry,
  type SearchDetail,
  searchQuery,
  useCancelSearch,
  useDeleteSearch,
} from "./novelty";
import { details } from "./NoveltyListPage";
import styles from "./NoveltyPage.module.css";

/** A refutation move found less often than this is marked as hard to find. */
const HARD = 0.5;

/** One novelty search: how far it got, and its tries, each on a board with its refutation. */
export function NoveltyPage() {
  const searchId = Number(useParams().searchId);
  const search = useQuery(searchQuery(searchId));

  if (search.isError) {
    const notFound = search.error instanceof ApiError && search.error.status === 404;
    return <p role="alert">{t(notFound ? "novelty.notFound" : "novelty.loadFailed")}</p>;
  }
  if (!search.data) {
    return null;
  }
  return <SearchView search={search.data} />;
}

function SearchView({ search }: { search: SearchDetail }) {
  const [chosen, setChosen] = useState(0);
  const shown = search.tries[chosen] ?? search.tries[0];

  return (
    <>
      <header className={styles.header}>
        <p className={styles.back}>
          <Link to="/novelty">{t("novelty.all")}</Link>
        </p>
        <h1 className={styles.title}>{search.start_label || t("novelty.unnamed")}</h1>
        <p className={styles.details}>
          {details(search)} ·{" "}
          {t("novelty.riskShort", { pawns: (search.budget_cp / 100).toFixed(2) })}
        </p>
        <p role="status" className={styles.status}>
          {statusText(search)}
        </p>
        <Actions search={search} />
      </header>
      {search.tries.length === 0 ? (
        <p className={styles.muted}>
          {isActive(search) ? t("novelty.noTriesYet") : t("novelty.noTries")}
        </p>
      ) : (
        <div className={styles.layout}>
          {shown && <TryBoard search={search} found={shown} />}
          <div className={styles.side}>
            <h2 className={styles.heading}>{t("novelty.tries")}</h2>
            <ol className={styles.tries}>
              {search.tries.map((found, index) => (
                <li key={found.rank}>
                  <TryButton
                    search={search}
                    found={found}
                    isChosen={found === shown}
                    onPress={() => {
                      setChosen(index);
                    }}
                  />
                </li>
              ))}
            </ol>
            {shown && <Refutation search={search} found={shown} />}
          </div>
        </div>
      )}
    </>
  );
}

function statusText(search: SearchDetail): string {
  if (search.status === "running" && search.started_at) {
    const end = new Date(new Date(search.started_at).getTime() + search.limit_minutes * 60_000);
    const time = end.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    return t("novelty.running", { moves: search.own_moves, time });
  }
  if (search.status === "failed") {
    return t("novelty.failedWith", { error: search.error });
  }
  return t(`novelty.status.${search.status}`, { moves: search.own_moves });
}

/** Cancel a search that waits or runs; delete one that has ended. */
function Actions({ search }: { search: SearchDetail }) {
  const cancel = useCancelSearch(search.id);
  const remove = useDeleteSearch(search.id);
  const navigate = useNavigate();
  const error = cancel.error ?? remove.error;
  return (
    <div className={styles.actions}>
      {isActive(search) ? (
        <Button
          className={styles.button}
          isPending={cancel.isPending}
          onPress={() => {
            cancel.mutate(undefined);
          }}
        >
          {t("novelty.stop")}
        </Button>
      ) : (
        <ModalDialog trigger={<Button className={styles.button}>{t("novelty.delete")}</Button>}>
          <Dialog className={dialogs.dialog} role="alertdialog">
            {({ close }) => (
              <div className={dialogs.form}>
                <Heading slot="title" className={dialogs.title}>
                  {t("novelty.deleteTitle")}
                </Heading>
                <div className={dialogs.buttons}>
                  <Button className={dialogs.secondary} onPress={close}>
                    {t("novelty.cancel")}
                  </Button>
                  <Button
                    className={dialogs.danger}
                    isPending={remove.isPending}
                    onPress={() => {
                      remove.mutate(undefined, {
                        onSuccess: () => {
                          void navigate("/novelty");
                        },
                      });
                    }}
                  >
                    {t("novelty.delete")}
                  </Button>
                </div>
              </div>
            )}
          </Dialog>
        </ModalDialog>
      )}
      {error && (
        <p className={styles.error} role="alert">
          {errorMessage(error)}
        </p>
      )}
    </div>
  );
}

/** A try in the list: its line, and how it compares with the engine's move. */
function TryButton(props: {
  search: SearchDetail;
  found: NoveltyTry;
  isChosen: boolean;
  onPress: () => void;
}) {
  const [notation] = useNotation();
  const format = notation === "figurines" ? withFigurines : undefined;
  const moves = tryMoves(props.search.start_fen, props.found.line, props.found.uci);
  return (
    <Button
      className={styles.try}
      aria-pressed={props.isChosen}
      // Named in letters even when it shows figurines, which screen readers read badly.
      aria-label={`${lineText(moves)}: ${summary(props.found)}`}
      onPress={props.onPress}
    >
      <span className={styles.line}>{lineText(moves, format)}</span>
      <span className={styles.summary}>{summary(props.found, format)}</span>
    </Button>
  );
}

function summary(found: NoveltyTry, format: (san: string) => string = (san) => san): string {
  return t("novelty.summary", {
    practical: percent(found.practical),
    best: percent(found.best_practical),
    move: format(found.best_san),
    eval: pawns(found.cp),
  });
}

/** The position before the try, with the try as an arrow. */
function TryBoard({ search, found }: { search: SearchDetail; found: NoveltyTry }) {
  const before = playedMoves(search.start_fen, found.line);
  const last = before.at(-1);
  const moves = tryMoves(search.start_fen, found.line, found.uci);
  return (
    <div className={styles.board}>
      <Board
        fen={last?.fen ?? search.start_fen}
        orientation={search.side}
        lastMove={last ? squaresOf(last.uci) : undefined}
        arrows={[
          {
            from: found.uci.slice(0, 2) as SquareName,
            to: found.uci.slice(2, 4) as SquareName,
            best: true,
          },
        ]}
        label={t("novelty.boardLabel", { line: lineText(moves) })}
      />
    </div>
  );
}

/** The refutation after the try, its hard moves marked, and whether a reference database has
 * the position. */
function Refutation({ search, found }: { search: SearchDetail; found: NoveltyTry }) {
  const [notation] = useNotation();
  const format = notation === "figurines" ? withFigurines : (san: string) => san;
  const before = tryMoves(search.start_fen, found.line, found.uci);
  const after = before.at(-1)?.fen ?? search.start_fen;
  const steps = playedMoves(
    after,
    found.refutation.map((step) => step.uci),
  );
  // How likely the opponent finds every one of their moves (ours have no probability).
  const refuted = found.refutation.reduce((all, step) => all * (step.found ?? 1), 1);
  return (
    <section aria-labelledby="refutation-heading" className={styles.refutation}>
      <h2 id="refutation-heading" className={styles.heading}>
        {t("novelty.refutation")}
      </h2>
      <p className={styles.muted}>
        {t("novelty.refuted", { chance: percent(refuted) })}{" "}
        {found.reference_games === null
          ? ""
          : found.reference_games === 0
            ? t("novelty.newInReference")
            : t("novelty.inReference", { count: found.reference_games })}
      </p>
      <ol className={styles.steps}>
        {found.refutation.map((step, index) => {
          const move = steps[index];
          const hard = step.found !== null && step.found < HARD;
          return (
            <li
              key={`${String(index)}-${step.uci}`}
              className={styles.step}
              data-theirs={step.found !== null || undefined}
              data-hard={hard || undefined}
            >
              <span aria-label={move ? lineText([move]) : step.san}>
                {move ? lineText([move], format) : format(step.san)}
              </span>
              {step.found !== null && (
                <span className={styles.found}>
                  {t(hard ? "novelty.foundHard" : "novelty.found", {
                    chance: percent(step.found),
                  })}
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
