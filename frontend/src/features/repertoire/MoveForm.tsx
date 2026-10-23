import { useState } from "react";
import { Button, Form, type FormProps, Input, Label, TextField } from "react-aria-components";

import { t } from "../../lib/i18n";
import { typedMove } from "../training";
import styles from "./MoveForm.module.css";

interface MoveFormProps {
  label: string;
  /** The position the move is played in. */
  fen: string;
  /** Called with a legal move, as UCI. */
  onMove: (uci: string) => void;
  isDisabled?: boolean;
}

/** Moves typed in, for the keyboard and screen readers: "Nf3" or "g1f3". */
export function MoveForm({ label, fen, onMove, isDisabled }: MoveFormProps) {
  const [text, setText] = useState("");
  const [invalid, setInvalid] = useState(false);

  const handleSubmit: FormProps["onSubmit"] = (event) => {
    event.preventDefault();
    const uci = typedMove(fen, text);
    setInvalid(uci === null);
    if (uci !== null) {
      setText("");
      onMove(uci);
    }
  };

  return (
    <Form className={styles.form} onSubmit={handleSubmit}>
      <TextField
        className={styles.field}
        value={text}
        onChange={(value) => {
          setText(value);
          setInvalid(false);
        }}
      >
        <Label className={styles.label}>{label}</Label>
        <Input className={styles.input} autoComplete="off" spellCheck={false} />
      </TextField>
      <Button className={styles.button} type="submit" isDisabled={isDisabled}>
        {t("drill.play")}
      </Button>
      {/* role="alert": screen readers announce it as soon as it appears. */}
      {invalid && (
        <p className={styles.error} role="alert">
          {t("drill.notLegal")}
        </p>
      )}
    </Form>
  );
}
