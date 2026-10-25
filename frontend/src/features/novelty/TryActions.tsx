import { useQuery } from "@tanstack/react-query";
import { INITIAL_FEN } from "chessops/fen";
import { useState } from "react";
import { Button, Dialog, Heading, Input, Label, TextField } from "react-aria-components";
import { Link } from "react-router";

import { dialogStyles as dialogs, ModalDialog } from "../../components/Dialog";
import { Select } from "../../components/Select";
import { t } from "../../lib/i18n";
import { playedMoves, StartGameDialog } from "../play";
import { repertoiresQuery } from "../repertoire";
import { errorMessage } from "./errors";
import { lineText, tryMoves } from "./lines";
import { type LineMove, type NoveltyTry, type SearchDetail, useAddToRepertoire } from "./novelty";
import styles from "./NoveltyPage.module.css";

/** What can be done with a try: play it out against Maia, or learn it as a repertoire line. */
export function TryActions({ search, found }: { search: SearchDetail; found: NoveltyTry }) {
  const moves = tryMoves(search.start_fen, found.line, found.uci);
  const after = moves.at(-1)?.fen ?? search.start_fen;
  const label = `${search.start_label ? `${search.start_label}: ` : ""}${lineText(moves)}`;
  return (
    <div className={styles.actions}>
      <StartGameDialog
        startFen={after}
        startLabel={label}
        side={search.side}
        rating={search.elo}
        triggerLabel={t("novelty.playIt")}
        triggerClassName={styles.button}
      />
      <AddToRepertoireDialog search={search} found={found} name={lineText(moves)} />
    </div>
  );
}

/**
 * The moves of a try as a repertoire line from the starting position: those that led to the
 * search's start, the line to the try, the try, and the refutation. Null if the moves to the
 * start aren't known (a search from a position typed in or set up).
 */
function repertoireMoves(search: SearchDetail, found: NoveltyTry): LineMove[] | null {
  const all = [
    ...search.start_moves,
    ...found.line,
    found.uci,
    ...found.refutation.map((step) => step.uci),
  ];
  const played = playedMoves(INITIAL_FEN, search.start_moves);
  if ((played.at(-1)?.fen ?? INITIAL_FEN) !== search.start_fen) {
    return null;
  }
  const positions = [INITIAL_FEN, ...playedMoves(INITIAL_FEN, all).map((move) => move.fen)];
  return all.map((uci, index) => ({ fen: positions[index] ?? INITIAL_FEN, uci }));
}

function AddToRepertoireDialog(props: { search: SearchDetail; found: NoveltyTry; name: string }) {
  const moves = repertoireMoves(props.search, props.found);
  if (moves === null) {
    return <p className={styles.muted}>{t("novelty.noRepertoire")}</p>;
  }
  return (
    <ModalDialog
      trigger={<Button className={styles.button}>{t("novelty.addToRepertoire")}</Button>}
    >
      <Dialog className={dialogs.dialog}>
        {({ close }) => <AddForm {...props} moves={moves} onClose={close} />}
      </Dialog>
    </ModalDialog>
  );
}

function AddForm(props: {
  search: SearchDetail;
  name: string;
  moves: LineMove[];
  onClose: () => void;
}) {
  const repertoires = useQuery(repertoiresQuery);
  const fitting = (repertoires.data ?? []).filter((r) => r.color === props.search.side);
  const [chosen, setChosen] = useState<string | null>(null);
  const [name, setName] = useState(props.name.slice(0, 100));
  const add = useAddToRepertoire();
  const repertoireId = chosen ?? (fitting[0] ? String(fitting[0].id) : null);

  return (
    <div className={dialogs.form}>
      <Heading slot="title" className={dialogs.title}>
        {t("novelty.addTitle")}
      </Heading>
      <p className={dialogs.note}>{t("novelty.addText")}</p>
      {fitting.length === 0 ? (
        <p className={dialogs.note}>{t(`novelty.noRepertoireFor.${props.search.side}`)}</p>
      ) : (
        <>
          <Select
            label={t("novelty.repertoire")}
            options={fitting.map((r) => ({ id: String(r.id), name: r.name }))}
            value={repertoireId}
            onChange={setChosen}
            anyOption={t("novelty.chooseRepertoire")}
          />
          <TextField className={dialogs.field} value={name} onChange={setName} maxLength={100}>
            <Label>{t("novelty.lineName")}</Label>
            <Input className={dialogs.input} />
          </TextField>
        </>
      )}
      {add.data && repertoireId && (
        <p role="status">
          {t("novelty.added")}{" "}
          <Link to={`/repertoires/${repertoireId}?line=${String(add.data.id)}`}>
            {t("novelty.openLine")}
          </Link>
        </p>
      )}
      {add.error && (
        <p className={dialogs.error} role="alert">
          {errorMessage(add.error)}
        </p>
      )}
      <div className={dialogs.buttons}>
        <Button className={dialogs.secondary} onPress={props.onClose}>
          {add.data ? t("novelty.close") : t("novelty.cancel")}
        </Button>
        {!add.data && (
          <Button
            className={dialogs.primary}
            isDisabled={repertoireId === null || name.trim() === ""}
            isPending={add.isPending}
            onPress={() => {
              if (repertoireId !== null) {
                add.mutate({
                  repertoireId: Number(repertoireId),
                  name: name.trim(),
                  moves: props.moves,
                });
              }
            }}
          >
            {t("novelty.add")}
          </Button>
        )}
      </div>
    </div>
  );
}
