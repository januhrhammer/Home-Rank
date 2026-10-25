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
import { type Opponent, opponentsQuery, useStartGame } from "./play";

const START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

/** Clocks to choose from, in minutes and seconds per move; "" is no clock. */
const CLOCKS = ["", "3+2", "5+3", "10+5", "15+10", "30+20"];

interface StartGameDialogProps {
  /** The position to play from; the starting position if not given. */
  startFen?: string;
  /** What the position is, to name the game: e.g. "Sicilian, after 1. e4 c5". */
  startLabel?: string;
  /** The side the user is likely to want, e.g. a repertoire's colour. */
  side?: "white" | "black";
  /** Maia's rating at first, e.g. a novelty search's opponent's. */
  rating?: number;
  /** The button that opens the dialog: "New game" or "Play from here". */
  triggerLabel?: string;
  triggerClassName?: string;
}

/** Choose a side, an opponent and a clock, and start a game against a bot. */
export function StartGameDialog(props: StartGameDialogProps) {
  const trigger = (
    <Button className={props.triggerClassName ?? dialogs.primary}>
      {props.triggerLabel ?? t("play.new")}
    </Button>
  );
  return (
    <ModalDialog trigger={trigger}>
      <Dialog className={dialogs.dialog}>
        {({ close }) => <StartForm {...props} onCancel={close} />}
      </Dialog>
    </ModalDialog>
  );
}

function StartForm({
  startFen = START,
  startLabel = "",
  side = "white",
  rating: initialRating = 1500,
  onCancel,
}: StartGameDialogProps & { onCancel: () => void }) {
  const opponents = useQuery(opponentsQuery);
  const [color, setColor] = useState(side);
  const [opponent, setOpponent] = useState<Opponent>("maia");
  const [rating, setRating] = useState(initialRating);
  const [clock, setClock] = useState("");
  const start = useStartGame();
  const navigate = useNavigate();

  const range = opponents.data?.find((option) => option.opponent === opponent);

  const handleSubmit: FormProps["onSubmit"] = (event) => {
    event.preventDefault();
    const [minutes, increment] = clock.split("+").map(Number);
    start.mutate(
      {
        start_fen: startFen,
        start_label: startLabel,
        user_color: color,
        opponent,
        opponent_elo: rating,
        clock:
          minutes === undefined || increment === undefined
            ? null
            : { base_seconds: minutes * 60, increment_seconds: increment },
      },
      {
        onSuccess: (game) => {
          void navigate(`/play/${String(game.id)}`);
        },
      },
    );
  };

  return (
    <Form className={dialogs.form} onSubmit={handleSubmit}>
      <Heading slot="title" className={dialogs.title}>
        {t("play.startTitle")}
      </Heading>
      {startLabel && <p className={dialogs.note}>{startLabel}</p>}
      <RadioGroup
        className={dialogs.field}
        value={color}
        onChange={(value) => {
          setColor(value === "black" ? "black" : "white");
        }}
      >
        <Label>{t("play.yourSide")}</Label>
        <div className={dialogs.radios}>
          <RadioField value="white">
            <RadioButton className={dialogs.radio}>{t("play.white")}</RadioButton>
          </RadioField>
          <RadioField value="black">
            <RadioButton className={dialogs.radio}>{t("play.black")}</RadioButton>
          </RadioField>
        </div>
      </RadioGroup>
      <RadioGroup
        className={dialogs.field}
        value={opponent}
        onChange={(value) => {
          const next = value === "stockfish" ? "stockfish" : "maia";
          setOpponent(next);
          // Keep the rating within what the new opponent plays.
          const nextRange = opponents.data?.find((option) => option.opponent === next);
          if (nextRange) {
            setRating(Math.min(nextRange.max_elo, Math.max(nextRange.min_elo, rating)));
          }
        }}
      >
        <Label>{t("play.opponent")}</Label>
        <div className={dialogs.radios}>
          <RadioField value="maia">
            <RadioButton className={dialogs.radio}>{t("play.opponent.maia")}</RadioButton>
          </RadioField>
          <RadioField value="stockfish">
            <RadioButton className={dialogs.radio}>{t("play.opponent.stockfish")}</RadioButton>
          </RadioField>
        </div>
      </RadioGroup>
      <p className={dialogs.note}>{t(`play.opponentText.${opponent}`)}</p>
      <NumberField
        className={dialogs.field}
        value={rating}
        onChange={setRating}
        minValue={range?.min_elo}
        maxValue={range?.max_elo}
        step={50}
        formatOptions={{ useGrouping: false }} // 1500, not 1,500
        isRequired
      >
        <Label>{t("play.rating")}</Label>
        <Input className={dialogs.input} />
      </NumberField>
      <RadioGroup className={dialogs.field} value={clock} onChange={setClock}>
        <Label>{t("play.clock")}</Label>
        <div className={dialogs.radios}>
          {CLOCKS.map((option) => (
            <RadioField key={option} value={option}>
              <RadioButton className={dialogs.radio}>
                {option === "" ? t("play.untimed") : option.replace("+", " + ")}
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
          {t("play.cancel")}
        </Button>
        <Button
          className={dialogs.primary}
          type="submit"
          isPending={start.isPending}
          isDisabled={range === undefined}
        >
          {t("play.start")}
        </Button>
      </div>
    </Form>
  );
}
