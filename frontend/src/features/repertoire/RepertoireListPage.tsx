import { useQuery } from "@tanstack/react-query";
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
  RadioButton,
  RadioField,
  RadioGroup,
  TextField,
} from "react-aria-components";
import { Link, useNavigate } from "react-router";

import { dialogStyles as dialogs, ModalDialog } from "../../components/Dialog";
import { t } from "../../lib/i18n";
import { errorMessage } from "./errors";
import { type Color, repertoiresQuery, useCreateRepertoire } from "./repertoire";
import styles from "./RepertoireListPage.module.css";

/** The user's repertoires, to open one or start a new one. */
export function RepertoireListPage() {
  const repertoires = useQuery(repertoiresQuery);
  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1>{t("repertoire.title")}</h1>
        <CreateDialog />
      </div>
      <p className={styles.intro}>{t("repertoire.intro")}</p>
      {repertoires.isError && <p role="alert">{t("repertoire.loadFailed")}</p>}
      {repertoires.data?.length === 0 && <p className={styles.none}>{t("repertoire.none")}</p>}
      <ul className={styles.list}>
        {repertoires.data?.map((repertoire) => (
          <li key={repertoire.id} className={styles.item}>
            <Link className={styles.name} to={`/repertoires/${String(repertoire.id)}`}>
              {repertoire.name}
            </Link>
            <span className={styles.details}>
              {t(`repertoire.for.${repertoire.color}`)} ·{" "}
              {t("repertoire.moveCount", { count: repertoire.move_count })}
              {repertoire.due > 0 && ` · ${t("repertoire.due", { count: repertoire.due })}`}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function CreateDialog() {
  return (
    <ModalDialog trigger={<Button className={dialogs.primary}>{t("repertoire.new")}</Button>}>
      <Dialog className={dialogs.dialog}>{({ close }) => <CreateForm onDone={close} />}</Dialog>
    </ModalDialog>
  );
}

function CreateForm({ onDone }: { onDone: () => void }) {
  const [name, setName] = useState("");
  const [color, setColor] = useState<Color>("white");
  const create = useCreateRepertoire();
  const navigate = useNavigate();

  const handleSubmit: FormProps["onSubmit"] = (event) => {
    event.preventDefault();
    create.mutate(
      { name: name.trim(), color },
      {
        onSuccess: (repertoire) => {
          onDone();
          void navigate(`/repertoires/${String(repertoire.id)}`);
        },
      },
    );
  };

  return (
    <Form className={dialogs.form} onSubmit={handleSubmit}>
      <Heading slot="title" className={dialogs.title}>
        {t("repertoire.new")}
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
      <RadioGroup
        className={dialogs.field}
        value={color}
        onChange={(value) => {
          setColor(value === "black" ? "black" : "white");
        }}
      >
        <Label>{t("repertoire.color")}</Label>
        <div className={dialogs.radios}>
          <RadioField value="white">
            <RadioButton className={dialogs.radio}>{t("repertoire.white")}</RadioButton>
          </RadioField>
          <RadioField value="black">
            <RadioButton className={dialogs.radio}>{t("repertoire.black")}</RadioButton>
          </RadioField>
        </div>
      </RadioGroup>
      {create.error && (
        <p className={dialogs.error} role="alert">
          {errorMessage(create.error)}
        </p>
      )}
      <div className={dialogs.buttons}>
        <Button className={dialogs.secondary} onPress={onDone}>
          {t("repertoire.cancel")}
        </Button>
        <Button className={dialogs.primary} type="submit" isPending={create.isPending}>
          {t("repertoire.create")}
        </Button>
      </div>
    </Form>
  );
}
