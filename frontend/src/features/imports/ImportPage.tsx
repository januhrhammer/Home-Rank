import { useState } from "react";
import {
  Button,
  Disclosure,
  DisclosurePanel,
  DropZone,
  type DropZoneProps,
  FileTrigger,
  Heading,
  ProgressBar,
  Text,
} from "react-aria-components";

import { t } from "../../lib/i18n";
import styles from "./ImportPage.module.css";
import { type Import, isActive, uploadErrorMessage, useImports, useUpload } from "./imports";

const dates = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });

export function ImportPage() {
  const upload = useUpload();
  const [wrongType, setWrongType] = useState(false);

  function start(file: File) {
    upload.reset(); // forget the previous file's error
    // The server checks this too; checking here saves uploading a large file for nothing.
    const isPgn = file.name.toLowerCase().endsWith(".pgn");
    setWrongType(!isPgn);
    if (isPgn) {
      upload.mutate(file);
    }
  }

  const error = wrongType
    ? t("import.wrongType")
    : upload.isError
      ? uploadErrorMessage(upload.error)
      : null;

  return (
    <>
      <h1>{t("import.title")}</h1>
      <p className={styles.intro}>{t("import.intro")}</p>
      <UploadZone onFile={start} isDisabled={upload.isPending} />
      {upload.isPending && (
        // role="status": screen readers announce it without interrupting.
        <p role="status">{t("import.uploading", { name: upload.variables.name })}</p>
      )}
      {error && (
        <p className={styles.error} role="alert">
          {error}
        </p>
      )}
      <h2>{t("import.history")}</h2>
      <ImportList />
    </>
  );
}

/** Drop a file on it, or choose one; both work with the keyboard too. */
function UploadZone({ onFile, isDisabled }: { onFile: (file: File) => void; isDisabled: boolean }) {
  const handleDrop: DropZoneProps["onDrop"] = (event) => {
    const item = event.items.find((dropped) => dropped.kind === "file");
    if (item?.kind === "file") {
      void item.getFile().then(onFile);
    }
  };

  return (
    <DropZone className={styles.dropZone} isDisabled={isDisabled} onDrop={handleDrop}>
      <Text slot="label">{t("import.drop")}</Text>{" "}
      <FileTrigger
        acceptedFileTypes={[".pgn"]}
        onSelect={(files) => {
          const file = files?.[0];
          if (file) {
            onFile(file);
          }
        }}
      >
        <Button className={styles.choose} isDisabled={isDisabled}>
          {t("import.choose")}
        </Button>
      </FileTrigger>
    </DropZone>
  );
}

function ImportList() {
  const imports = useImports();

  if (imports.isPending) {
    return null;
  }
  if (imports.isError) {
    return (
      <p className={styles.error} role="alert">
        {t("import.loadFailed")}
      </p>
    );
  }
  if (imports.data.length === 0) {
    return <p>{t("import.none")}</p>;
  }
  return (
    <ul className={styles.list}>
      {imports.data.map((run) => (
        <ImportItem key={run.id} run={run} />
      ))}
    </ul>
  );
}

function ImportItem({ run }: { run: Import }) {
  return (
    <li className={styles.item}>
      <div className={styles.itemHeader}>
        <span className={styles.fileName}>{run.file_name}</span>
        <span className={styles.status} data-status={run.status}>
          {t(`import.status.${run.status}`)}
        </span>
      </div>
      <time className={styles.date} dateTime={run.created_at}>
        {dates.format(new Date(run.created_at))}
      </time>
      {isActive(run) && <Progress run={run} />}
      <p className={styles.counts}>
        {t("import.counts", {
          imported: run.games_imported,
          duplicates: run.games_duplicate,
          failed: run.games_failed,
        })}
      </p>
      {run.errors.length > 0 && <Problems run={run} />}
    </li>
  );
}

function Progress({ run }: { run: Import }) {
  const percent = run.file_size > 0 ? (run.bytes_read / run.file_size) * 100 : 0;
  return (
    <ProgressBar
      className={styles.progress}
      aria-label={t("import.progress", { name: run.file_name })}
      value={percent}
      // Until the worker starts, there is no progress to show yet.
      isIndeterminate={run.status === "queued"}
    >
      {({ percentage, isIndeterminate }) => (
        <div className={styles.track}>
          {isIndeterminate ? (
            <div className={styles.fill} data-waiting />
          ) : (
            <div className={styles.fill} style={{ width: `${String(percentage ?? 0)}%` }} />
          )}
        </div>
      )}
    </ProgressBar>
  );
}

/** The import's first problems, collapsed until asked for. */
function Problems({ run }: { run: Import }) {
  return (
    <Disclosure className={styles.problems}>
      <Heading level={3} className={styles.problemsHeading}>
        <Button slot="trigger" className={styles.problemsButton}>
          <span className={styles.chevron} aria-hidden="true">
            ▸
          </span>
          {t("import.problems", { count: run.errors.length })}
        </Button>
      </Heading>
      <DisclosurePanel>
        <ul className={styles.problemList}>
          {run.errors.map((error) => (
            <li key={`${String(error.line)}:${error.reason}`}>
              {error.line === null
                ? error.reason
                : t("import.problemAtLine", { line: error.line, reason: error.reason })}
            </li>
          ))}
        </ul>
      </DisclosurePanel>
    </Disclosure>
  );
}
