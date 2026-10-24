import { useState } from "react";
import { Button, Label, TextArea, TextField, ToggleButton } from "react-aria-components";

import { type MessageKey, t } from "../../lib/i18n";
import { isMainLine, MOVE_MARKS, POSITION_MARKS } from "./annotate";
import styles from "./AnnotationTools.module.css";
import { type MoveNode, moveNumber, SYMBOLS } from "./moveTree";

/** What each mark means, for screen readers and as a tooltip. */
const MARK_NAMES: Record<number, MessageKey> = {
  1: "annotate.nag.good",
  2: "annotate.nag.mistake",
  3: "annotate.nag.brilliant",
  4: "annotate.nag.blunder",
  5: "annotate.nag.interesting",
  6: "annotate.nag.dubious",
  10: "annotate.nag.equal",
  14: "annotate.nag.whiteSlightly",
  15: "annotate.nag.blackSlightly",
  16: "annotate.nag.whiteBetter",
  17: "annotate.nag.blackBetter",
  18: "annotate.nag.whiteWinning",
  19: "annotate.nag.blackWinning",
};

interface AnnotationToolsProps {
  /** The move shown; null is the starting position. */
  current: MoveNode | null;
  /** How to write a move: with figurines or letters. */
  format: (san: string) => string;
  onComment: (text: string) => void;
  onMark: (nag: number) => void;
  onDelete: () => void;
  isSaving: boolean;
}

/** Comment on the move shown, mark it, or delete it if it is a variation (ADR 0019). */
export function AnnotationTools({ current, format, ...props }: AnnotationToolsProps) {
  if (current === null) {
    return <p className={styles.hint}>{t("annotate.hint")}</p>;
  }
  const move = `${moveNumber(current)} ${format(current.san)}`;
  return (
    <div className={styles.tools}>
      {/* A new comment field for each move, filled with its comment. */}
      <CommentField key={current.path.join(".")} move={move} current={current} {...props} />
      <MarkButtons label={t("annotate.moveMarks")} nags={MOVE_MARKS} current={current} {...props} />
      <MarkButtons
        label={t("annotate.positionMarks")}
        nags={POSITION_MARKS}
        current={current}
        {...props}
      />
      {!isMainLine(current.path) && (
        <Button className={styles.button} isDisabled={props.isSaving} onPress={props.onDelete}>
          {t("annotate.delete")}
        </Button>
      )}
      <p className={styles.hint}>{t("annotate.variationHint")}</p>
    </div>
  );
}

function CommentField({
  move,
  current,
  onComment,
  isSaving,
}: Pick<AnnotationToolsProps, "onComment" | "isSaving"> & { move: string; current: MoveNode }) {
  const saved = current.commentsAfter.join(" ");
  const [text, setText] = useState(saved);
  return (
    <div className={styles.comment}>
      <TextField className={styles.field} value={text} onChange={setText}>
        <Label className={styles.label}>{t("annotate.comment", { move })}</Label>
        <TextArea className={styles.textArea} rows={3} />
      </TextField>
      <Button
        className={styles.button}
        isDisabled={text.trim() === saved.trim() || isSaving}
        onPress={() => {
          onComment(text);
        }}
      >
        {t("annotate.saveComment")}
      </Button>
    </div>
  );
}

function MarkButtons({
  label,
  nags,
  current,
  onMark,
  isSaving,
}: Pick<AnnotationToolsProps, "onMark" | "isSaving"> & {
  label: string;
  nags: number[];
  current: MoveNode;
}) {
  return (
    <div className={styles.marks} role="group" aria-label={label}>
      {nags.map((nag) => {
        const symbol = SYMBOLS[nag] ?? "";
        return (
          <ToggleButton
            key={nag}
            className={styles.mark}
            isSelected={current.symbols.includes(symbol)}
            isDisabled={isSaving}
            aria-label={MARK_NAMES[nag] ? t(MARK_NAMES[nag]) : symbol}
            onChange={() => {
              onMark(nag);
            }}
          >
            {symbol}
          </ToggleButton>
        );
      })}
    </div>
  );
}
