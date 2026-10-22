import { useState } from "react";

/** How moves are written: with figurines (♘f3), as chess books do, or letters (Nf3). */
export type Notation = "figurines" | "letters";

const FIGURINES: Record<string, string> = { K: "♔", Q: "♕", R: "♖", B: "♗", N: "♘" };

/**
 * A move in SAN with figurines instead of piece letters: "Nf3" → "♘f3", "exd8=Q" → "exd8=♕".
 * The letters are a move's first character, or the piece a pawn becomes.
 */
export function withFigurines(san: string): string {
  return san.replace(/^[KQRBN]|(?<==)[QRBN]/g, (letter) => FIGURINES[letter] ?? letter);
}

const STORAGE_KEY = "home-rank.notation";

/**
 * The notation this browser shows, figurines unless letters were chosen. The choice is kept
 * in the browser (localStorage): it's about reading, and needs no account.
 */
export function useNotation(): [Notation, (notation: Notation) => void] {
  const [notation, setNotation] = useState(storedNotation);
  const change = (next: Notation) => {
    setNotation(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Storage can be blocked (private windows, strict settings): then it lasts this visit.
    }
  };
  return [notation, change];
}

function storedNotation(): Notation {
  try {
    return localStorage.getItem(STORAGE_KEY) === "letters" ? "letters" : "figurines";
  } catch {
    return "figurines";
  }
}
