import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import {
  Button,
  Form,
  type FormProps,
  Input,
  Label,
  NumberField,
  SwitchButton,
  SwitchField,
  Text,
  TextArea,
  TextField,
} from "react-aria-components";

import { ApiError } from "../../api/errors";
import { t } from "../../lib/i18n";
import { type AnalysisSettings, analysisSettingsQuery, useSaveAnalysisSettings } from "../analysis";
import { type Settings, settingsQuery, useSaveSettings } from "./settings";
import styles from "./SettingsPage.module.css";

export function SettingsPage() {
  const settings = useQuery(settingsQuery);

  return (
    <div className={styles.page}>
      <h1>{t("settings.title")}</h1>
      {settings.isError && <p role="alert">{t("settings.loadFailed")}</p>}
      {settings.data && <PlayerNames settings={settings.data} />}
      <AnalysisSection />
    </div>
  );
}

/** One name per line, as the user types them; the server tidies them up when saving. */
function PlayerNames({ settings }: { settings: Settings }) {
  const save = useSaveSettings();
  const [text, setText] = useState(settings.player_names.join("\n"));

  // Typed by React Aria's Form itself: React's types and React Aria's currently disagree on
  // the name of the submit event type.
  const handleSubmit: FormProps["onSubmit"] = (event) => {
    event.preventDefault();
    save.mutate(
      { player_names: text.split("\n") },
      {
        onSuccess: (saved) => {
          setText(saved.player_names.join("\n"));
        },
      },
    );
  };

  return (
    <section aria-labelledby="player-names-heading">
      <h2 id="player-names-heading">{t("settings.playerNames.title")}</h2>
      <p className={styles.intro}>{t("settings.playerNames.intro")}</p>
      <Form className={styles.form} onSubmit={handleSubmit}>
        <TextField
          className={styles.field}
          value={text}
          onChange={(value) => {
            setText(value);
            save.reset(); // a new change: "Saved" no longer applies
          }}
        >
          <Label>{t("settings.playerNames.label")}</Label>
          <TextArea className={styles.textArea} rows={5} spellCheck={false} />
          <Text slot="description" className={styles.hint}>
            {t("settings.playerNames.hint")}
          </Text>
        </TextField>
        <div className={styles.actions}>
          <Button className={styles.button} type="submit" isPending={save.isPending}>
            {t("settings.save")}
          </Button>
          {/* role="status": screen readers announce it without interrupting. */}
          <span role="status" className={styles.status}>
            {save.isSuccess && t("settings.playerNames.saved")}
          </span>
        </div>
        {save.isError && (
          <p className={styles.error} role="alert">
            {t("settings.saveFailed")}
          </p>
        )}
      </Form>
    </section>
  );
}

function AnalysisSection() {
  const settings = useQuery(analysisSettingsQuery);
  return (
    <section aria-labelledby="analysis-settings-heading">
      <h2 id="analysis-settings-heading">{t("settings.analysis.title")}</h2>
      {settings.isError && <p role="alert">{t("settings.loadFailed")}</p>}
      {settings.data && <AnalysisForm settings={settings.data} />}
    </section>
  );
}

const THRESHOLDS = ["inaccuracy", "mistake", "blunder"] as const;

/** Automatic analysis on or off, and how much a move may lose before it counts as weak. */
function AnalysisForm({ settings }: { settings: AnalysisSettings }) {
  const save = useSaveAnalysisSettings();
  const [values, setValues] = useState(settings);

  const change = (changes: Partial<AnalysisSettings>) => {
    setValues((current) => ({ ...current, ...changes }));
    save.reset(); // a new change: "Saved" no longer applies
  };

  const handleSubmit: FormProps["onSubmit"] = (event) => {
    event.preventDefault();
    save.mutate(values);
  };

  const error =
    save.error instanceof ApiError && save.error.status === 422
      ? t("settings.analysis.order")
      : t("settings.saveFailed");

  return (
    <Form className={styles.form} onSubmit={handleSubmit}>
      <SwitchField
        isSelected={values.auto_analyse}
        onChange={(on) => {
          change({ auto_analyse: on });
        }}
      >
        <SwitchButton className={styles.switch}>
          <span className={styles.track}>
            <span className={styles.thumb} />
          </span>
          {t("settings.analysis.auto")}
        </SwitchButton>
      </SwitchField>
      <p className={styles.hint}>{t("settings.analysis.autoHint")}</p>
      <p className={styles.intro}>{t("settings.analysis.thresholds")}</p>
      <div className={styles.thresholds}>
        {THRESHOLDS.map((name) => (
          <NumberField
            key={name}
            className={styles.field}
            value={values[name]}
            minValue={1}
            maxValue={100}
            step={1}
            onChange={(value) => {
              change({ [name]: value });
            }}
          >
            <Label>{t(`settings.analysis.${name}`)}</Label>
            <Input className={styles.number} />
          </NumberField>
        ))}
      </div>
      <div className={styles.actions}>
        <Button className={styles.button} type="submit" isPending={save.isPending}>
          {t("settings.save")}
        </Button>
        <span role="status" className={styles.status}>
          {save.isSuccess && t("settings.analysis.saved")}
        </span>
      </div>
      {save.isError && (
        <p className={styles.error} role="alert">
          {error}
        </p>
      )}
    </Form>
  );
}
