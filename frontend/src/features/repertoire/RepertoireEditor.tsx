import { useMemo, useState } from "react";
import {
  Button,
  Dialog,
  Form,
  type FormProps,
  Heading,
  Label,
  TextArea,
  TextField,
} from "react-aria-components";
import { Link } from "react-router";

import { Board } from "../../components/Board";
import { dialogStyles as dialogs, ModalDialog } from "../../components/Dialog";
import { BackIcon, EndIcon, FlipIcon, ForwardIcon, StartIcon } from "../../components/Icons";
import { t } from "../../lib/i18n";
import { useKeyboard } from "../../lib/useKeyboard";
import { arrowsOf, EnginePanel, useLiveAnalysis } from "../engine";
import { ExplorerPanel, type Source } from "../explorer";
import { MoveList, type MoveNode, useNotation, withFigurines } from "../games";
import { FindTriesDialog } from "../novelty";
import { StartGameDialog } from "../play";
import { boardMove, legalDests, turnOf } from "../training";
import { errorMessage } from "./errors";
import { MoveForm } from "./MoveForm";
import {
  type Repertoire,
  type RepertoireLine,
  type RepertoireMove,
  useAddMove,
  useCommentMove,
  useRemoveMove,
} from "./repertoire";
import styles from "./RepertoireEditor.module.css";
import { buildRepertoireTree, lineTo, type RepertoireTree, START_FEN } from "./tree";

interface RepertoireEditorProps {
  repertoire: Repertoire;
  /** The line shown and edited. */
  line: RepertoireLine;
  lines: RepertoireLine[];
  /** All of the repertoire's moves, of every line. */
  moves: RepertoireMove[];
}

/**
 * One line of the repertoire on a board: moves played on it (or chosen in the explorer) are
 * added to the line, moves already there are followed. The move list shows the line's tree;
 * the other lines' moves in the shown position are listed below it.
 */
export function RepertoireEditor({ repertoire, line, lines, moves }: RepertoireEditorProps) {
  const [notation] = useNotation();
  const lineMoves = useMemo(
    () => moves.filter((move) => move.line_ids.includes(line.id)),
    [moves, line.id],
  );
  const tree = useMemo(
    () => buildRepertoireTree(lineMoves, notation === "figurines" ? withFigurines : undefined),
    [lineMoves, notation],
  );
  // The move whose position is shown, by id, so it survives the tree being rebuilt after a
  // change; null is the starting position.
  const [currentId, setCurrentId] = useState<number | null>(null);
  const current = currentId === null ? null : (tree.byId.get(currentId) ?? null);
  const [flipped, setFlipped] = useState(false);
  const [explorerSource, setExplorerSource] = useState<Source>({ kind: "mine" });
  const addMove = useAddMove(repertoire.id);

  const fen = current?.fen ?? START_FEN;
  const orientation = (repertoire.color === "black") !== flipped ? "black" : "white";
  const live = useLiveAnalysis(fen);
  const format = (san: string) => (notation === "figurines" ? withFigurines(san) : san);
  // The moves from the shown position, wherever the tree shows them (a transposition's are
  // shown under the other way there).
  const shownAt = current ? (tree.transposesTo.get(current.id) ?? current) : null;
  const nextMoves = shownAt ? shownAt.children : tree.firstMoves;

  // The other lines' moves from the shown position, which this line doesn't have.
  const position = shownAt
    ? tree.moves.get(shownAt.id)?.to_position
    : moves.find((move) => move.from_fen === START_FEN)?.from_position;
  const lineNames = new Map(lines.map((each) => [each.id, each.name]));
  const linesOf = (move: RepertoireMove) =>
    move.line_ids.map((id) => lineNames.get(id) ?? "").join(", ");
  const elsewhere = moves.filter(
    (move) => move.from_position === position && !move.line_ids.includes(line.id),
  );

  const play = (uci: string) => {
    const known = nextMoves.find((node) => tree.moves.get(node.id)?.move_uci === uci);
    if (known) {
      setCurrentId(known.id);
      return;
    }
    addMove.mutate(
      { fen, move_uci: uci, line_id: line.id },
      {
        onSuccess: (move) => {
          setCurrentId(move.id);
        },
      },
    );
  };

  const go = {
    start: () => {
      setCurrentId(null);
    },
    back: () => {
      setCurrentId(current?.parent?.id ?? null);
    },
    forward: () => {
      const next = nextMoves[0];
      if (next) {
        setCurrentId(next.id);
      }
    },
    end: () => {
      setCurrentId(endOfLine(tree, current)?.id ?? null);
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

  return (
    <div className={styles.editor}>
      <div className={styles.boardColumn}>
        <Board
          fen={fen}
          orientation={orientation}
          lastMove={current?.squares}
          arrows={arrowsOf(live.lines)}
          label={
            current
              ? t("repertoire.positionAfter", { line: lineTo(current) })
              : t("viewer.startingPosition")
          }
          movable={
            addMove.isPending
              ? undefined
              : {
                  color: turnOf(fen),
                  dests: legalDests(fen),
                  onMove: (from, to) => {
                    play(boardMove(fen, from, to, ""));
                  },
                }
          }
        />
        <div className={styles.controls}>
          <Button className={styles.control} aria-label={t("viewer.start")} onPress={go.start}>
            <StartIcon />
          </Button>
          <Button className={styles.control} aria-label={t("viewer.back")} onPress={go.back}>
            <BackIcon />
          </Button>
          <Button className={styles.control} aria-label={t("viewer.forward")} onPress={go.forward}>
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
        <MoveForm
          label={t("repertoire.typeMove")}
          fen={fen}
          onMove={play}
          isDisabled={addMove.isPending}
        />
        <p className={styles.hint}>{t("repertoire.boardHint")}</p>
        <StartGameDialog
          startFen={fen}
          startLabel={
            current
              ? t("play.labelAfter", { start: repertoire.name, line: lineTo(current) })
              : repertoire.name
          }
          side={repertoire.color}
          triggerLabel={t("play.newFrom")}
          triggerClassName={styles.control}
        />
        <FindTriesDialog
          fen={fen}
          moves={movesTo(tree, current)}
          label={
            current
              ? t("play.labelAfter", { start: repertoire.name, line: lineTo(current) })
              : repertoire.name
          }
          side={repertoire.color}
          triggerClassName={styles.control}
        />
        {addMove.error && (
          <p className={styles.error} role="alert">
            {errorMessage(addMove.error)}
          </p>
        )}
      </div>
      <div className={styles.sideColumn}>
        <EnginePanel fen={fen} analysis={live} />
        <section aria-labelledby="moves-heading">
          <h2 id="moves-heading" className={styles.heading}>
            {t("repertoire.moves")}
          </h2>
          {tree.firstMoves.length === 0 ? (
            <p className={styles.muted}>{t("repertoire.empty")}</p>
          ) : (
            <MoveList
              tree={tree}
              current={current}
              onSelect={(node) => {
                setCurrentId(node.id);
              }}
              notation={notation}
            />
          )}
        </section>
        {elsewhere.length > 0 && (
          <section aria-labelledby="elsewhere-heading">
            <h2 id="elsewhere-heading" className={styles.heading}>
              {t("repertoire.otherLines")}
            </h2>
            <ul className={styles.elsewhere}>
              {elsewhere.map((move) => (
                <li key={move.id}>
                  <Button
                    className={styles.linkButton}
                    isDisabled={addMove.isPending}
                    // Named in letters even when it shows figurines, which screen readers read badly.
                    aria-label={t("repertoire.inLines", {
                      move: move.move_san,
                      lines: linesOf(move),
                    })}
                    onPress={() => {
                      play(move.move_uci);
                    }}
                  >
                    {t("repertoire.inLines", { move: format(move.move_san), lines: linesOf(move) })}
                  </Button>
                </li>
              ))}
            </ul>
            <p className={styles.muted}>{t("repertoire.otherLinesHint")}</p>
          </section>
        )}
        {current && (
          <CurrentMove
            key={current.id}
            repertoireId={repertoire.id}
            line={line}
            node={current}
            move={tree.moves.get(current.id)}
            transposesTo={tree.transposesTo.get(current.id)}
            format={format}
            onGo={setCurrentId}
          />
        )}
        <section aria-labelledby="explorer-heading">
          <h2 id="explorer-heading" className={styles.heading}>
            {t("explorer.title")}
          </h2>
          <ExplorerPanel
            fen={fen}
            source={explorerSource}
            onSourceChange={setExplorerSource}
            formatMove={format}
            onMove={(move) => {
              if (!addMove.isPending) {
                play(move.uci);
              }
            }}
          />
          <p className={styles.muted}>{t("repertoire.explorerHint")}</p>
        </section>
      </div>
    </div>
  );
}

/** The moves (UCI) from the start to a node, for searches that start there. */
function movesTo(tree: RepertoireTree, node: MoveNode | null): string[] {
  const moves: string[] = [];
  for (let at = node; at !== null; at = at.parent) {
    const move = tree.moves.get(at.id);
    if (move === undefined) {
      return [];
    }
    moves.unshift(move.move_uci);
  }
  return moves;
}

/** The last move of the line on from a node, following the first move at each position. */
function endOfLine(tree: RepertoireTree, node: MoveNode | null): MoveNode | null {
  let at = node;
  const seen = new Set<number>();
  for (;;) {
    const shown = at ? (tree.transposesTo.get(at.id) ?? at) : null;
    const next = (shown ? shown.children : tree.firstMoves)[0];
    if (next === undefined || seen.has(next.id)) {
      return at;
    }
    seen.add(next.id);
    at = next;
  }
}

interface CurrentMoveProps {
  repertoireId: number;
  line: RepertoireLine;
  node: MoveNode;
  move: RepertoireMove | undefined;
  transposesTo: MoveNode | undefined;
  format: (san: string) => string;
  onGo: (moveId: number | null) => void;
}

/** The shown move: its comment, where it transposes to, and removing it. */
function CurrentMove({
  repertoireId,
  line: repertoireLine,
  node,
  move,
  transposesTo,
  format,
  onGo,
}: CurrentMoveProps) {
  const [comment, setComment] = useState(move?.comment ?? "");
  const save = useCommentMove(repertoireId);
  const line = lineTo(node, format);

  const handleSubmit: FormProps["onSubmit"] = (event) => {
    event.preventDefault();
    save.mutate({ moveId: node.id, comment });
  };

  return (
    <section aria-labelledby="current-heading" className={styles.current}>
      {/* Named in letters even when it shows figurines, which screen readers read badly. */}
      <h2 id="current-heading" className={styles.heading} aria-label={lineTo(node)}>
        {line}
      </h2>
      <p className={styles.muted}>
        {move?.card_id === null ? t("repertoire.opponentsMove") : t("repertoire.yourMove")}
      </p>
      {transposesTo && (
        <Button
          className={styles.linkButton}
          aria-label={t("repertoire.continueAt", { line: lineTo(transposesTo) })}
          onPress={() => {
            onGo(transposesTo.id);
          }}
        >
          {t("repertoire.continueAt", { line: lineTo(transposesTo, format) })}
        </Button>
      )}
      <Form className={styles.commentForm} onSubmit={handleSubmit}>
        <TextField className={styles.field} value={comment} onChange={setComment} maxLength={2000}>
          <Label className={styles.label}>{t("repertoire.comment")}</Label>
          <TextArea className={styles.textarea} rows={3} />
        </TextField>
        <div className={styles.buttons}>
          <Button className={styles.button} type="submit" isPending={save.isPending}>
            {t("repertoire.saveComment")}
          </Button>
          <Link
            className={styles.button}
            to={`/repertoires/${String(repertoireId)}/drill?mode=line&through=${String(node.id)}`}
          >
            {t("repertoire.drillHere")}
          </Link>
          <RemoveDialog
            repertoireId={repertoireId}
            repertoireLine={repertoireLine}
            node={node}
            line={line}
            onRemoved={() => {
              onGo(node.parent?.id ?? null);
            }}
          />
        </div>
        <p role="status" className={styles.muted}>
          {save.isSuccess && t("repertoire.commentSaved")}
        </p>
        {save.error && (
          <p className={styles.error} role="alert">
            {errorMessage(save.error)}
          </p>
        )}
      </Form>
    </section>
  );
}

function RemoveDialog(props: {
  repertoireId: number;
  repertoireLine: RepertoireLine;
  node: MoveNode;
  line: string;
  onRemoved: () => void;
}) {
  const remove = useRemoveMove(props.repertoireId);
  return (
    <ModalDialog trigger={<Button className={styles.button}>{t("repertoire.removeMove")}</Button>}>
      <Dialog className={dialogs.dialog} role="alertdialog">
        {({ close }) => (
          <div className={dialogs.form}>
            <Heading slot="title" className={dialogs.title}>
              {t("repertoire.removeTitle", { line: props.line, name: props.repertoireLine.name })}
            </Heading>
            <p>{t("repertoire.removeText")}</p>
            {remove.error && (
              <p className={dialogs.error} role="alert">
                {errorMessage(remove.error)}
              </p>
            )}
            <div className={dialogs.buttons}>
              <Button className={dialogs.secondary} onPress={close}>
                {t("repertoire.cancel")}
              </Button>
              <Button
                className={dialogs.danger}
                isPending={remove.isPending}
                onPress={() => {
                  remove.mutate(
                    { moveId: props.node.id, lineId: props.repertoireLine.id },
                    {
                      onSuccess: () => {
                        close();
                        props.onRemoved();
                      },
                    },
                  );
                }}
              >
                {t("repertoire.remove")}
              </Button>
            </div>
          </div>
        )}
      </Dialog>
    </ModalDialog>
  );
}
