import { useState } from "react";
import {
  Button,
  Dialog,
  FieldError,
  Form,
  type FormProps,
  Heading,
  Input,
  Label,
  TextField,
} from "react-aria-components";
import { Link } from "react-router";

import { dialogStyles as dialogs, ModalDialog } from "../../components/Dialog";
import { t } from "../../lib/i18n";
import { errorMessage } from "./errors";
import styles from "./LinesPanel.module.css";
import {
  type Repertoire,
  type RepertoireLine,
  type RepertoireMove,
  useCreateLine,
  useDeleteLine,
  useRenameLine,
  useReorderLines,
} from "./repertoire";

interface LinesPanelProps {
  repertoire: Repertoire;
  lines: RepertoireLine[];
  moves: RepertoireMove[];
  current: RepertoireLine;
  /** Show another line; null shows the first. */
  onSelect: (lineId: number | null) => void;
}

/** The repertoire's lines (ADR 0020): which one the editor shows, and managing them. */
export function LinesPanel({ repertoire, lines, moves, current, onSelect }: LinesPanelProps) {
  const reorder = useReorderLines(repertoire.id);
  const index = lines.findIndex((line) => line.id === current.id);
  const move = (by: -1 | 1) => {
    const ids = lines.map((line) => line.id);
    const other = ids[index + by];
    if (other !== undefined) {
      ids[index + by] = current.id;
      ids[index] = other;
      reorder.mutate(ids);
    }
  };

  return (
    <section aria-labelledby="lines-heading" className={styles.panel}>
      <h2 id="lines-heading" className={styles.heading}>
        {t("repertoire.lines")}
      </h2>
      <ul className={styles.list}>
        {lines.map((line) => (
          <li key={line.id}>
            <Link
              to={`?line=${String(line.id)}`}
              className={line.id === current.id ? styles.current : styles.line}
              aria-current={line.id === current.id ? "page" : undefined}
            >
              {line.name} <span className={styles.count}>{line.move_count}</span>
            </Link>
          </li>
        ))}
      </ul>
      <div className={styles.actions}>
        <NewLineDialog repertoire={repertoire} onCreated={onSelect} />
        <RenameLineDialog repertoireId={repertoire.id} line={current} />
        <Button
          className={styles.action}
          isDisabled={index <= 0 || reorder.isPending}
          onPress={() => {
            move(-1);
          }}
        >
          {t("repertoire.lineUp")}
        </Button>
        <Button
          className={styles.action}
          isDisabled={index >= lines.length - 1 || reorder.isPending}
          onPress={() => {
            move(1);
          }}
        >
          {t("repertoire.lineDown")}
        </Button>
        {lines.length > 1 && (
          <DeleteLineDialog
            repertoireId={repertoire.id}
            line={current}
            moves={moves}
            onDeleted={() => {
              onSelect(null);
            }}
          />
        )}
      </div>
      {reorder.error && (
        <p className={styles.error} role="alert">
          {errorMessage(reorder.error)}
        </p>
      )}
      <p className={styles.hint}>{t("repertoire.linesHint")}</p>
    </section>
  );
}

function NewLineDialog(props: { repertoire: Repertoire; onCreated: (lineId: number) => void }) {
  const create = useCreateLine(props.repertoire.id);
  return (
    <ModalDialog trigger={<Button className={styles.action}>{t("repertoire.newLine")}</Button>}>
      <Dialog className={dialogs.dialog}>
        {({ close }) => (
          <NameForm
            title={t("repertoire.newLineTitle", { name: props.repertoire.name })}
            initial=""
            submitLabel={t("repertoire.create")}
            mutation={create}
            onDone={(line) => {
              close();
              props.onCreated(line.id);
            }}
            onCancel={close}
          />
        )}
      </Dialog>
    </ModalDialog>
  );
}

function RenameLineDialog(props: { repertoireId: number; line: RepertoireLine }) {
  const rename = useRenameLine(props.repertoireId, props.line.id);
  return (
    <ModalDialog trigger={<Button className={styles.action}>{t("repertoire.renameLine")}</Button>}>
      <Dialog className={dialogs.dialog}>
        {({ close }) => (
          <NameForm
            title={t("repertoire.renameLine")}
            initial={props.line.name}
            submitLabel={t("repertoire.save")}
            mutation={rename}
            onDone={close}
            onCancel={close}
          />
        )}
      </Dialog>
    </ModalDialog>
  );
}

function NameForm(props: {
  title: string;
  initial: string;
  submitLabel: string;
  mutation: ReturnType<typeof useCreateLine>;
  onDone: (line: RepertoireLine) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(props.initial);
  const handleSubmit: FormProps["onSubmit"] = (event) => {
    event.preventDefault();
    props.mutation.mutate(name.trim(), { onSuccess: props.onDone });
  };
  return (
    <Form className={dialogs.form} onSubmit={handleSubmit}>
      <Heading slot="title" className={dialogs.title}>
        {props.title}
      </Heading>
      <TextField
        className={dialogs.field}
        value={name}
        onChange={setName}
        isRequired
        maxLength={100}
      >
        <Label>{t("repertoire.lineName")}</Label>
        <Input className={dialogs.input} />
        <FieldError className={dialogs.error} />
      </TextField>
      {props.mutation.error && (
        <p className={dialogs.error} role="alert">
          {errorMessage(props.mutation.error)}
        </p>
      )}
      <div className={dialogs.buttons}>
        <Button className={dialogs.secondary} onPress={props.onCancel}>
          {t("repertoire.cancel")}
        </Button>
        <Button className={dialogs.primary} type="submit" isPending={props.mutation.isPending}>
          {props.submitLabel}
        </Button>
      </div>
    </Form>
  );
}

/** Asks before deleting a line, and says how many moves go with it. */
function DeleteLineDialog(props: {
  repertoireId: number;
  line: RepertoireLine;
  moves: RepertoireMove[];
  onDeleted: () => void;
}) {
  const remove = useDeleteLine(props.repertoireId, props.line.id);
  // The moves no other line has: the server deletes those.
  const own = props.moves.filter(
    (move) => move.line_ids.length === 1 && move.line_ids[0] === props.line.id,
  ).length;
  return (
    <ModalDialog trigger={<Button className={styles.action}>{t("repertoire.deleteLine")}</Button>}>
      <Dialog className={dialogs.dialog} role="alertdialog">
        {({ close }) => (
          <div className={dialogs.form}>
            <Heading slot="title" className={dialogs.title}>
              {t("repertoire.deleteLineTitle", { name: props.line.name })}
            </Heading>
            <p>
              {own > 0
                ? t("repertoire.deleteLineText", { count: own })
                : t("repertoire.deleteLineShared")}
            </p>
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
                  remove.mutate(undefined, {
                    onSuccess: () => {
                      close();
                      props.onDeleted();
                    },
                  });
                }}
              >
                {t("repertoire.delete")}
              </Button>
            </div>
          </div>
        )}
      </Dialog>
    </ModalDialog>
  );
}
