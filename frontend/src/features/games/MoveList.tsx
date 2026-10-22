import { type ReactNode, useEffect, useRef } from "react";

import { t } from "../../lib/i18n";
import styles from "./MoveList.module.css";
import { type MoveNode, moveNumber, type MoveTree } from "./moveTree";
import { type Notation, withFigurines } from "./notation";

interface MoveListProps {
  tree: MoveTree;
  /** The move whose position is shown; null for the starting position. */
  current: MoveNode | null;
  onSelect: (move: MoveNode) => void;
  notation: Notation;
}

/**
 * The moves as chess books print them: variations in parentheses, comments in between. A
 * variation of the game's own moves gets a line of its own; deeper ones run on inside it.
 */
export function MoveList({ tree, current, onSelect, notation }: MoveListProps) {
  return (
    <div className={styles.moves} role="group" aria-label={t("viewer.moves")}>
      {tree.gameComments.map((comment) => (
        <p key={comment} className={styles.gameComment}>
          {comment}
        </p>
      ))}
      <Line
        candidates={tree.firstMoves}
        depth={0}
        current={current}
        onSelect={onSelect}
        notation={notation}
      />
    </div>
  );
}

interface LineProps extends Omit<MoveListProps, "tree"> {
  /** The moves possible at the line's start: the first is played, the others are variations. */
  candidates: MoveNode[];
  /** 0 for the game's own moves, 1 for a variation of them, and so on. */
  depth: number;
}

function Line({ candidates, depth, current, onSelect, notation }: LineProps) {
  const items: ReactNode[] = [];
  let next = candidates;
  let withNumber = true; // a line always starts with a move number, even for a Black move
  while (next[0] !== undefined) {
    const [played, ...variations] = next;
    items.push(
      <Move
        key={played.id}
        move={played}
        withNumber={withNumber || played.ply % 2 === 1}
        isCurrent={played === current}
        onSelect={onSelect}
        notation={notation}
      />,
    );
    for (const variation of variations) {
      items.push(
        <span
          key={`variation-${String(variation.id)}`}
          className={depth === 0 ? styles.ownLine : styles.variation}
        >
          (
          <Line
            candidates={[variation]}
            depth={depth + 1}
            current={current}
            onSelect={onSelect}
            notation={notation}
          />
          )
        </span>,
      );
    }
    // After a variation or a comment, Black's move gets its number again ("12… Nf6").
    withNumber = variations.length > 0 || played.commentsAfter.length > 0;
    next = played.children;
  }
  return <>{items}</>;
}

interface MoveProps {
  move: MoveNode;
  withNumber: boolean;
  isCurrent: boolean;
  onSelect: (move: MoveNode) => void;
  notation: Notation;
}

function Move({ move, withNumber, isCurrent, onSelect, notation }: MoveProps) {
  const buttonRef = useRef<HTMLButtonElement>(null);

  // Keep the current move in view while stepping through a long game.
  useEffect(() => {
    if (isCurrent) {
      buttonRef.current?.scrollIntoView({ block: "nearest" });
    }
  }, [isCurrent]);

  return (
    <>
      {move.commentsBefore.map((comment) => (
        <span key={comment} className={styles.comment}>
          {comment}
        </span>
      ))}
      {withNumber && <span className={styles.number}>{moveNumber(move)}</span>}
      <button
        ref={buttonRef}
        type="button"
        className={styles.move}
        // Named in letters even when it shows figurines: screen readers say "Nf3" clearly,
        // while "♘f3" comes out as "white chess knight f3", or not at all.
        aria-label={move.san + move.symbols.join("")}
        aria-current={isCurrent ? "step" : undefined}
        onClick={() => {
          onSelect(move);
        }}
      >
        {notation === "figurines" ? withFigurines(move.san) : move.san}
        {move.symbols.join("")}
      </button>
      {move.commentsAfter.map((comment) => (
        <span key={comment} className={styles.comment}>
          {comment}
        </span>
      ))}
    </>
  );
}
