import { useState } from "react";
import {
  Button,
  Form,
  type FormProps,
  Input,
  Label,
  ProgressBar,
  RadioButton,
  RadioField,
  RadioGroup,
  SwitchButton,
  SwitchField,
  TextField,
} from "react-aria-components";
import { Link } from "react-router";

import { t } from "../../lib/i18n";
import styles from "./LinkedAccounts.module.css";
import {
  isActive,
  type LinkedAccount,
  linkErrorMessage,
  type Platform,
  PLATFORMS,
  type SyncRun,
  useAccounts,
  useLinkAccount,
  useSetEnabled,
  useSyncNow,
  useUnlink,
} from "./sync";

const dates = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });

/** The user's Lichess and Chess.com accounts: link them, see how their syncs went. */
export function LinkedAccounts() {
  return (
    <section aria-labelledby="linked-accounts-heading">
      <h2 id="linked-accounts-heading">{t("sync.title")}</h2>
      <p className={styles.intro}>{t("sync.intro")}</p>
      <AccountList />
      <LinkForm />
    </section>
  );
}

function AccountList() {
  const accounts = useAccounts();
  const syncNow = useSyncNow();
  const setEnabled = useSetEnabled();
  const unlink = useUnlink();

  if (accounts.isPending) {
    return null;
  }
  if (accounts.isError) {
    return (
      <p className={styles.error} role="alert">
        {t("sync.loadFailed")}
      </p>
    );
  }
  const failed = syncNow.isError || setEnabled.isError || unlink.isError;
  return (
    <>
      {accounts.data.length === 0 ? (
        <p>{t("sync.none")}</p>
      ) : (
        <ul className={styles.list}>
          {accounts.data.map((account) => (
            <li
              key={account.id}
              className={styles.item}
              aria-label={t("sync.accountLabel", {
                platform: t(`sync.platform.${account.platform}`),
                username: account.username,
              })}
            >
              <div className={styles.itemHeader}>
                <span className={styles.name}>
                  {t(`sync.platform.${account.platform}`)} · {account.username}
                </span>
                <div className={styles.actions}>
                  <Button
                    className={styles.button}
                    isDisabled={isActive(account.last_run)}
                    onPress={() => {
                      syncNow.mutate(account.id);
                    }}
                  >
                    {t("sync.syncNow")}
                  </Button>
                  <Button
                    className={styles.button}
                    onPress={() => {
                      unlink.mutate(account.id);
                    }}
                  >
                    {t("sync.unlink")}
                  </Button>
                </div>
              </div>
              <RunStatus account={account} />
              <SwitchField
                isSelected={account.enabled}
                onChange={(enabled) => {
                  setEnabled.mutate({ id: account.id, enabled });
                }}
              >
                <SwitchButton className={styles.switch}>
                  <span className={styles.track}>
                    <span className={styles.thumb} />
                  </span>
                  {t("sync.auto")}
                </SwitchButton>
              </SwitchField>
            </li>
          ))}
        </ul>
      )}
      {failed && (
        <p className={styles.error} role="alert">
          {t("sync.actionFailed")}
        </p>
      )}
    </>
  );
}

/** How the account's newest sync went, or how far it has got. */
function RunStatus({ account }: { account: LinkedAccount }) {
  const run = account.last_run;
  if (run === null) {
    return <p className={styles.status}>{t("sync.never")}</p>;
  }
  if (isActive(run)) {
    return (
      <>
        <p className={styles.status}>
          {run.status === "queued"
            ? t("sync.status.queued")
            : t("sync.status.running", { imported: run.games_imported })}
        </p>
        <ProgressBar
          className={styles.progress}
          aria-label={t("sync.progress", { username: account.username })}
          // A sync can't know how many games are still to come.
          isIndeterminate
        >
          <div className={styles.progressTrack}>
            <div className={styles.progressFill} />
          </div>
        </ProgressBar>
      </>
    );
  }
  const date = dates.format(new Date(run.finished_at ?? run.created_at));
  const stopped = run.errors.find((error) => error.game === null);
  return (
    <>
      <p className={styles.status} data-status={run.status}>
        {t(`sync.status.${run.status === "failed" ? "failed" : "done"}`, { date })}
        {stopped && <> · {stopped.reason}</>}
      </p>
      <Counts run={run} />
      {/* The cursor moves once a sync has stored games (or, on Chess.com, read whole months). */}
      {(account.synced_until !== null || run.games_imported > 0) && (
        <Link className={styles.showGames} to={`/games?source=${account.platform}`}>
          {t("sync.showGames", { platform: t(`sync.platform.${account.platform}`) })}
        </Link>
      )}
    </>
  );
}

function Counts({ run }: { run: SyncRun }) {
  return (
    <p className={styles.counts}>
      {t("sync.counts", {
        imported: run.games_imported,
        duplicates: run.games_duplicate,
        failed: run.games_failed,
      })}
    </p>
  );
}

function LinkForm() {
  const link = useLinkAccount();
  const [platform, setPlatform] = useState<Platform>("lichess");
  const [username, setUsername] = useState("");

  // Typed by React Aria's Form itself: React's types and React Aria's currently disagree on
  // the name of the submit event type.
  const handleSubmit: FormProps["onSubmit"] = (event) => {
    event.preventDefault();
    link.mutate(
      { platform, username },
      {
        onSuccess: () => {
          setUsername("");
        },
      },
    );
  };

  return (
    <Form className={styles.form} onSubmit={handleSubmit}>
      <RadioGroup
        className={styles.platforms}
        orientation="horizontal"
        value={platform}
        onChange={(value) => {
          setPlatform(value as Platform);
        }}
      >
        <Label className={styles.label}>{t("sync.platform")}</Label>
        {PLATFORMS.map((choice) => (
          <RadioField key={choice} value={choice}>
            <RadioButton className={styles.radio}>{t(`sync.platform.${choice}`)}</RadioButton>
          </RadioField>
        ))}
      </RadioGroup>
      <TextField
        className={styles.field}
        value={username}
        onChange={(value) => {
          setUsername(value);
          link.reset(); // the error was about the name before
        }}
        isRequired
      >
        <Label className={styles.label}>{t("sync.username")}</Label>
        <Input className={styles.input} />
      </TextField>
      <Button className={styles.submit} type="submit" isPending={link.isPending}>
        {link.isPending ? t("sync.linking") : t("sync.link")}
      </Button>
      {link.isError && (
        <p className={styles.error} role="alert">
          {linkErrorMessage(link.error)}
        </p>
      )}
    </Form>
  );
}
