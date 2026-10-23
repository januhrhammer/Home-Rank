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

import { Board } from "../../components/Board";
import { dialogStyles as dialogs, ModalDialog } from "../../components/Dialog";
import { BackIcon, EndIcon, FlipIcon, ForwardIcon, StartIcon } from "../../components/Icons";
import { t } from "../../lib/i18n";
import { useKeyboard } from "../../lib/useKeyboard";
import { ExplorerPanel, type Source } from "../explorer";
import { MoveList, type MoveNode, useNotation, withFigurines } from "../games";
import { boardMove, legalDests, turnOf } from "../training";
import { errorMessage } from "./errors";
import {
  type Repertoire,
  type RepertoireMove,
  useAddMove,
  useCommentMove,
  useRemoveMove,
} from "./repertoire";
import styles from "./RepertoireEditor.module.css";
import { buildRepertoireTree, lineTo, type RepertoireTree, START_FEN } from "./tree";

interface RepertoireEditorProps {
  repertoire: Repertoire;
  moves: RepertoireMove[];
}

/**
 * The repertoire on a board: moves played on it (or chosen in the explorer) are added to the
 * repertoire, moves already there are followed. The move list shows the whole tree.
 */
export function RepertoireEditor({ repertoire, moves }: RepertoireEditorProps) {
  const [notation] = useNotation();
  const tree = useMemo(
    () => buildRepertoireTree(moves, notation === "figurines" ? withFigurines : undefined),
    [moves, notation],
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
  const format = (san: string) => (notation === "figurines" ? withFigurines(san) : san);
  // The moves from the shown position, wherever the tree shows them (a transposition's are
  // shown under the other way there).
  const shownAt = current ? (tree.transposesTo.get(current.id) ?? current) : null;
  const nextMoves = shownAt ? shownAt.children : tree.firstMoves;

  const play = (uci: string) => {
    const known = nextMoves.find((node) => tree.moves.get(node.id)?.move_uci === uci);
    if (known) {
      setCurrentId(known.id);
      return;
    }
    addMove.mutate(
      { fen, move_uci: uci },
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
        <p className={styles.hint}>{t("repertoire.boardHint")}</p>
        {addMove.error && (
          <p className={styles.error} role="alert">
            {errorMessage(addMove.error)}
          </p>
        )}
      </div>
      <div className={styles.sideColumn}>
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
        {current && (
          <CurrentMove
            key={current.id}
            repertoireId={repertoire.id}
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
  node: MoveNode;
  move: RepertoireMove | undefined;
  transposesTo: MoveNode | undefined;
  format: (san: string) => string;
  onGo: (moveId: number | null) => void;
}

/** The shown move: its comment, where it transposes to, and removing it. */
function CurrentMove({ repertoireId, node, move, transposesTo, format, onGo }: CurrentMoveProps) {
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
          <RemoveDialog
            repertoireId={repertoireId}
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
              {t("repertoire.removeTitle", { line: props.line })}
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
                  remove.mutate(props.node.id, {
                    onSuccess: () => {
                      close();
                      props.onRemoved();
                    },
                  });
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
