import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import {
  Button,
  Dialog,
  Form,
  type FormProps,
  Heading,
  Input,
  Label,
  NumberField,
  RadioButton,
  RadioField,
  RadioGroup,
} from "react-aria-components";
import { useNavigate } from "react-router";

import { dialogStyles as dialogs, ModalDialog } from "../../components/Dialog";
import { t } from "../../lib/i18n";
import { errorMessage } from "./errors";
import { type RatingKind, ratingQuery, useStartSearch } from "./novelty";

/** The time limits offered, in minutes: a quick look, between rounds, overnight. */
const LIMITS = [10, 60, 480] as const;

interface FindTriesDialogProps {
  /** The position to search from. */
  fen: string;
  /** The moves (UCI) from the starting position that led there, if known. */
  moves: string[];
  /** What the position is, e.g. "Smith-Morra, after 9.Rd1 e5". */
  label: string;
  /** The side to prepare for, at first. */
  side: "white" | "black";
  triggerClassName?: string;
}

/** Start a novelty search from a position (ADR 0022): the side, the opponent, the risk, the
 * time; then its page, where the tries come in. */
export function FindTriesDialog(props: FindTriesDialogProps) {
  return (
    <ModalDialog
      trigger={
        <Button className={props.triggerClassName ?? dialogs.secondary}>{t("novelty.find")}</Button>
      }
    >
      <Dialog className={dialogs.dialog}>
        {({ close }) => <FindTriesForm {...props} onCancel={close} />}
      </Dialog>
    </ModalDialog>
  );
}

function FindTriesForm({
  fen,
  moves,
  label,
  side,
  onCancel,
}: FindTriesDialogProps & { onCancel: () => void }) {
  const [color, setColor] = useState(side);
  const [rating, setRating] = useState(1800);
  const [kind, setKind] = useState<RatingKind>("fide");
  const [elo, setElo] = useState(Number.NaN); // NaN: the converted one
  const [pawns, setPawns] = useState(1.5);
  const [limit, setLimit] = useState<number>(60);
  const converted = useQuery(ratingQuery(Number.isNaN(rating) ? 0 : rating, kind));
  const start = useStartSearch();
  const navigate = useNavigate();

  const handleSubmit: FormProps["onSubmit"] = (event) => {
    event.preventDefault();
    start.mutate(
      {
        fen,
        moves,
        label,
        side: color,
        rating,
        rating_kind: kind,
        elo: Number.isNaN(elo) ? null : elo,
        budget_cp: Math.round(pawns * 100),
        limit_minutes: limit,
      },
      {
        onSuccess: (search) => {
          void navigate(`/novelty/${String(search.id)}`);
        },
      },
    );
  };

  return (
    <Form className={dialogs.form} onSubmit={handleSubmit}>
      <Heading slot="title" className={dialogs.title}>
        {t("novelty.findTitle")}
      </Heading>
      {label && <p className={dialogs.note}>{label}</p>}
      <p className={dialogs.note}>{t("novelty.findText")}</p>
      <RadioGroup
        className={dialogs.field}
        value={color}
        onChange={(value) => {
          setColor(value === "black" ? "black" : "white");
        }}
      >
        <Label>{t("novelty.side")}</Label>
        <div className={dialogs.radios}>
          <RadioField value="white">
            <RadioButton className={dialogs.radio}>{t("play.white")}</RadioButton>
          </RadioField>
          <RadioField value="black">
            <RadioButton className={dialogs.radio}>{t("play.black")}</RadioButton>
          </RadioField>
        </div>
      </RadioGroup>
      <NumberField
        className={dialogs.field}
        value={rating}
        onChange={setRating}
        minValue={0}
        maxValue={3500}
        formatOptions={{ useGrouping: false }} // 1800, not 1,800
        isRequired
      >
        <Label>{t("novelty.rating")}</Label>
        <Input className={dialogs.input} />
      </NumberField>
      <RadioGroup
        className={dialogs.field}
        value={kind}
        onChange={(value) => {
          setKind(value === "dwz" ? "dwz" : value === "lichess" ? "lichess" : "fide");
        }}
      >
        <Label>{t("novelty.ratingKind")}</Label>
        <div className={dialogs.radios}>
          <RadioField value="fide">
            <RadioButton className={dialogs.radio}>FIDE</RadioButton>
          </RadioField>
          <RadioField value="dwz">
            <RadioButton className={dialogs.radio}>DWZ</RadioButton>
          </RadioField>
          <RadioField value="lichess">
            <RadioButton className={dialogs.radio}>Lichess</RadioButton>
          </RadioField>
        </div>
      </RadioGroup>
      <p className={dialogs.note} role="status">
        {converted.data && t("novelty.maiaPlays", { elo: String(converted.data.elo) })}
      </p>
      <NumberField
        className={dialogs.field}
        value={elo}
        onChange={setElo}
        minValue={800}
        maxValue={2400}
        step={50}
        formatOptions={{ useGrouping: false }}
      >
        <Label>{t("novelty.ownElo")}</Label>
        <Input className={dialogs.input} />
      </NumberField>
      <NumberField
        className={dialogs.field}
        value={pawns}
        onChange={setPawns}
        minValue={0}
        maxValue={5}
        step={0.25}
        isRequired
      >
        <Label>{t("novelty.risk")}</Label>
        <Input className={dialogs.input} />
      </NumberField>
      <p className={dialogs.note}>{t("novelty.riskText")}</p>
      <RadioGroup
        className={dialogs.field}
        value={String(limit)}
        onChange={(value) => {
          setLimit(Number(value));
        }}
      >
        <Label>{t("novelty.time")}</Label>
        <div className={dialogs.radios}>
          {LIMITS.map((minutes) => (
            <RadioField key={minutes} value={String(minutes)}>
              <RadioButton className={dialogs.radio}>
                {t(`novelty.limit.${String(minutes) as "10" | "60" | "480"}`)}
              </RadioButton>
            </RadioField>
          ))}
        </div>
      </RadioGroup>
      {start.error && (
        <p className={dialogs.error} role="alert">
          {errorMessage(start.error)}
        </p>
      )}
      <div className={dialogs.buttons}>
        <Button className={dialogs.secondary} onPress={onCancel}>
          {t("novelty.cancel")}
        </Button>
        <Button className={dialogs.primary} type="submit" isPending={start.isPending}>
          {t("novelty.start")}
        </Button>
      </div>
    </Form>
  );
}
