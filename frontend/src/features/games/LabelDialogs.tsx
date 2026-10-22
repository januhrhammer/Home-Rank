import { type ReactNode, useState } from "react";
import {
  Button,
  Dialog,
  DialogTrigger,
  FieldError,
  Form,
  type FormProps,
  Heading,
  Input,
  Label,
  Modal,
  ModalOverlay,
  TextArea,
  TextField,
} from "react-aria-components";

import { t } from "../../lib/i18n";
import styles from "./LabelDialogs.module.css";
import {
  labelErrorMessage,
  type LabelFields,
  type LabelKind,
  useCreateLabel,
  useDeleteLabel,
  useUpdateLabel,
} from "./labels";

/** A modal dialog: it keeps the focus inside, closes with Escape, and tells screen readers. */
function ModalDialog({ trigger, children }: { trigger: ReactNode; children: ReactNode }) {
  return (
    <DialogTrigger>
      {trigger}
      <ModalOverlay className={styles.overlay} isDismissable>
        <Modal className={styles.modal}>{children}</Modal>
      </ModalOverlay>
    </DialogTrigger>
  );
}

interface EditDialogProps {
  kind: LabelKind;
  /** The tag or collection to change; without it, the dialog creates a new one. */
  label?: { id: number; name: string; description?: string };
  trigger: ReactNode;
}

export function EditDialog({ kind, label, trigger }: EditDialogProps) {
  return (
    <ModalDialog trigger={trigger}>
      <Dialog className={styles.dialog}>
        {({ close }) =>
          label ? (
            <UpdateForm kind={kind} label={label} onDone={close} />
          ) : (
            <CreateForm kind={kind} onDone={close} />
          )
        }
      </Dialog>
    </ModalDialog>
  );
}

function CreateForm({ kind, onDone }: { kind: LabelKind; onDone: () => void }) {
  const create = useCreateLabel(kind);
  return (
    <LabelForm
      kind={kind}
      title={t(`labels.new.${kind}`)}
      mutation={create}
      onSave={(fields) => {
        create.mutate(fields, { onSuccess: onDone });
      }}
      onCancel={onDone}
    />
  );
}

function UpdateForm(props: {
  kind: LabelKind;
  label: { id: number; name: string; description?: string };
  onDone: () => void;
}) {
  const update = useUpdateLabel(props.kind, props.label.id);
  return (
    <LabelForm
      kind={props.kind}
      title={t("labels.edit", { name: props.label.name })}
      initial={props.label}
      mutation={update}
      onSave={(fields) => {
        update.mutate(fields, { onSuccess: props.onDone });
      }}
      onCancel={props.onDone}
    />
  );
}

interface LabelFormProps {
  kind: LabelKind;
  title: string;
  initial?: LabelFields;
  mutation: { isPending: boolean; error: Error | null };
  onSave: (fields: LabelFields) => void;
  onCancel: () => void;
}

/** Name, and for collections a description; shared by creating and changing. */
function LabelForm({ kind, title, initial, mutation, onSave, onCancel }: LabelFormProps) {
  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");

  const handleSubmit: FormProps["onSubmit"] = (event) => {
    event.preventDefault();
    onSave(kind === "collections" ? { name: name.trim(), description } : { name: name.trim() });
  };

  return (
    <Form className={styles.form} onSubmit={handleSubmit}>
      <Heading slot="title" className={styles.title}>
        {title}
      </Heading>
      <TextField
        className={styles.field}
        value={name}
        onChange={setName}
        isRequired
        maxLength={kind === "tags" ? 50 : 100}
      >
        <Label>{t("labels.name")}</Label>
        <Input className={styles.input} />
        <FieldError className={styles.error} />
      </TextField>
      {kind === "collections" && (
        <TextField className={styles.field} value={description} onChange={setDescription}>
          <Label>{t("labels.description")}</Label>
          <TextArea className={styles.input} rows={3} />
        </TextField>
      )}
      {mutation.error && (
        <p className={styles.error} role="alert">
          {labelErrorMessage(mutation.error, name.trim())}
        </p>
      )}
      <div className={styles.buttons}>
        <Button className={styles.secondary} onPress={onCancel}>
          {t("labels.cancel")}
        </Button>
        <Button className={styles.primary} type="submit" isPending={mutation.isPending}>
          {t("labels.save")}
        </Button>
      </div>
    </Form>
  );
}

interface DeleteDialogProps {
  kind: LabelKind;
  label: { id: number; name: string };
  trigger: ReactNode;
}

/** Asks before deleting, and says that the games themselves stay. */
export function DeleteDialog({ kind, label, trigger }: DeleteDialogProps) {
  const remove = useDeleteLabel(kind, label.id);
  return (
    <ModalDialog trigger={trigger}>
      <Dialog className={styles.dialog} role="alertdialog">
        {({ close }) => (
          <div className={styles.form}>
            <Heading slot="title" className={styles.title}>
              {t("labels.deleteTitle", { name: label.name })}
            </Heading>
            <p>{t(`labels.deleteText.${kind}`)}</p>
            {remove.isError && (
              <p className={styles.error} role="alert">
                {t("labels.failed")}
              </p>
            )}
            <div className={styles.buttons}>
              <Button className={styles.secondary} onPress={close}>
                {t("labels.cancel")}
              </Button>
              <Button
                className={styles.danger}
                isPending={remove.isPending}
                onPress={() => {
                  remove.mutate(undefined, { onSuccess: close });
                }}
              >
                {t("labels.delete")}
              </Button>
            </div>
          </div>
        )}
      </Dialog>
    </ModalDialog>
  );
}
