import { expect, test } from "vitest";

import { t } from "./i18n";

test("returns the text for a key", () => {
  expect(t("app.name")).toBe("Home-Rank");
});

test("rejects unknown keys at compile time", () => {
  // @ts-expect-error -- tsc fails here if unknown keys were ever accepted silently
  expect(t("app.nmae")).toBeUndefined();
});
