import { useState } from "react";
import {
  Button,
  Dialog,
  FieldError,
  FileTrigger,
  Form,
  type FormProps,
  Heading,
  Input,
  Label,
  NumberField,
  TextField,
} from "react-aria-components";
import { useNavigate } from "react-router";

import { dialogStyles as dialogs, ModalDialog } from "../../components/Dialog";
import { t } from "../../lib/i18n";
import { errorMessage } from "./errors";
import {
  type Repertoire,
  useDeleteRepertoire,
  useImportPgn,
  useRenameRepertoire,
  useSeed,
} from "./repertoire";
import styles from "./RepertoirePage.module.css";

/** Add the moves of a PGN file, e.g. a course or a study exported from Lichess. */
export function ImportDialog({ repertoire }: { repertoire: Repertoire }) {
  const upload = useImportPgn(repertoire.id);
  const [file, setFile] = useState<File | null>(null);
  return (
    <ModalDialog trigger={<Button className={styles.action}>{t("repertoire.import")}</Button>}>
      <Dialog className={dialogs.dialog}>
        {({ close }) => (
          <div className={dialogs.form}>
            <Heading slot="title" className={dialogs.title}>
              {t("repertoire.importTitle")}
            </Heading>
            <p className={dialogs.note}>{t("repertoire.importText")}</p>
            <div>
              <FileTrigger
                acceptedFileTypes={[".pgn"]}
                onSelect={(files) => {
                  setFile(files?.[0] ?? null);
                  upload.reset();
                }}
              >
                <Button className={dialogs.secondary}>{t("repertoire.chooseFile")}</Button>
              </FileTrigger>{" "}
              <span className={dialogs.note}>{file?.name ?? t("repertoire.noFile")}</span>
            </div>
            {upload.data && (
              <p role="status">
                {t("repertoire.imported", {
                  moves: upload.data.moves_added,
                  games: upload.data.games_read,
                })}
                {upload.data.games_skipped > 0 &&
                  ` ${t("repertoire.importSkipped", { count: upload.data.games_skipped })}`}
              </p>
            )}
            {upload.error && (
              <p className={dialogs.error} role="alert">
                {errorMessage(upload.error)}
              </p>
            )}
            <div className={dialogs.buttons}>
              <Button className={dialogs.secondary} onPress={close}>
                {upload.data ? t("repertoire.close") : t("repertoire.cancel")}
              </Button>
              {!upload.data && (
                <Button
                  className={dialogs.primary}
                  isDisabled={file === null}
                  isPending={upload.isPending}
                  onPress={() => {
                    if (file) {
                      upload.mutate(file);
                    }
                  }}
                >
                  {t("repertoire.importButton")}
                </Button>
              )}
            </div>
          </div>
        )}
      </Dialog>
    </ModalDialog>
  );
}

/** Add what the user plays in their games with the repertoire's colour. */
export function SeedDialog({ repertoire }: { repertoire: Repertoire }) {
  const seed = useSeed(repertoire.id);
  const [depth, setDepth] = useState(12);
  const [minGames, setMinGames] = useState(2);

  const handleSubmit: FormProps["onSubmit"] = (event) => {
    event.preventDefault();
    seed.mutate({ depth, min_games: minGames });
  };

  return (
    <ModalDialog trigger={<Button className={styles.action}>{t("repertoire.seed")}</Button>}>
      <Dialog className={dialogs.dialog}>
        {({ close }) => (
          <Form className={dialogs.form} onSubmit={handleSubmit}>
            <Heading slot="title" className={dialogs.title}>
              {t("repertoire.seedTitle")}
            </Heading>
            <p className={dialogs.note}>{t(`repertoire.seedText.${repertoire.color}`)}</p>
            <NumberField
              className={dialogs.field}
              value={depth}
              onChange={setDepth}
              minValue={1}
              maxValue={30}
              isRequired
            >
              <Label>{t("repertoire.seedDepth")}</Label>
              <Input className={dialogs.input} />
            </NumberField>
            <NumberField
              className={dialogs.field}
              value={minGames}
              onChange={setMinGames}
              minValue={1}
              maxValue={1000}
              isRequired
            >
              <Label>{t("repertoire.seedMinGames")}</Label>
              <Input className={dialogs.input} />
            </NumberField>
            {seed.data && (
              <p role="status">{t("repertoire.seeded", { count: seed.data.moves_added })}</p>
            )}
            {seed.error && (
              <p className={dialogs.error} role="alert">
                {errorMessage(seed.error)}
              </p>
            )}
            <div className={dialogs.buttons}>
              <Button className={dialogs.secondary} onPress={close}>
                {seed.data ? t("repertoire.close") : t("repertoire.cancel")}
              </Button>
              {!seed.data && (
                <Button className={dialogs.primary} type="submit" isPending={seed.isPending}>
                  {t("repertoire.seedButton")}
                </Button>
              )}
            </div>
          </Form>
        )}
      </Dialog>
    </ModalDialog>
  );
}

export function RenameDialog({ repertoire }: { repertoire: Repertoire }) {
  const rename = useRenameRepertoire(repertoire.id);
  return (
    <ModalDialog trigger={<Button className={styles.action}>{t("repertoire.rename")}</Button>}>
      <Dialog className={dialogs.dialog}>
        {({ close }) => <RenameForm repertoire={repertoire} rename={rename} onDone={close} />}
      </Dialog>
    </ModalDialog>
  );
}

function RenameForm(props: {
  repertoire: Repertoire;
  rename: ReturnType<typeof useRenameRepertoire>;
  onDone: () => void;
}) {
  const [name, setName] = useState(props.repertoire.name);
  const handleSubmit: FormProps["onSubmit"] = (event) => {
    event.preventDefault();
    props.rename.mutate(name.trim(), { onSuccess: props.onDone });
  };
  return (
    <Form className={dialogs.form} onSubmit={handleSubmit}>
      <Heading slot="title" className={dialogs.title}>
        {t("repertoire.rename")}
      </Heading>
      <TextField
        className={dialogs.field}
        value={name}
        onChange={setName}
        isRequired
        maxLength={100}
      >
        <Label>{t("repertoire.name")}</Label>
        <Input className={dialogs.input} />
        <FieldError className={dialogs.error} />
      </TextField>
      {props.rename.error && (
        <p className={dialogs.error} role="alert">
          {errorMessage(props.rename.error)}
        </p>
      )}
      <div className={dialogs.buttons}>
        <Button className={dialogs.secondary} onPress={props.onDone}>
          {t("repertoire.cancel")}
        </Button>
        <Button className={dialogs.primary} type="submit" isPending={props.rename.isPending}>
          {t("repertoire.save")}
        </Button>
      </div>
    </Form>
  );
}

/** Asks before deleting, and says that the training history goes too. */
export function DeleteDialog({ repertoire }: { repertoire: Repertoire }) {
  const remove = useDeleteRepertoire(repertoire.id);
  const navigate = useNavigate();
  return (
    <ModalDialog trigger={<Button className={styles.action}>{t("repertoire.delete")}</Button>}>
      <Dialog className={dialogs.dialog} role="alertdialog">
        {({ close }) => (
          <div className={dialogs.form}>
            <Heading slot="title" className={dialogs.title}>
              {t("repertoire.deleteTitle", { name: repertoire.name })}
            </Heading>
            <p>{t("repertoire.deleteText")}</p>
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
                      void navigate("/repertoires");
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
