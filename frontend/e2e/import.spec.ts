import path from "node:path";

import { expect, test } from "@playwright/test";

/** Morphy's Opera Game, with a comment and a variation, and Fool's Mate. */
const PGN_FILE = path.join(import.meta.dirname, "fixtures", "two-games.pgn");

test("import a PGN file, step through a game, tag it and find it by its tag", async ({ page }) => {
  // Choose the file as a person does, in the browser's file dialog. The real file reaches the
  // server, which the unit tests can't check (see src/test/uploads.ts).
  await page.goto("/import");
  const fileChooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "choose a file" }).click();
  await (await fileChooser).setFiles(PGN_FILE);

  // The worker imports it in the background, while the page shows how far it got.
  const run = page.getByRole("listitem").filter({ hasText: "two-games.pgn" });
  await expect(run.getByText("Done")).toBeVisible({ timeout: 30_000 });
  await expect(run).toContainText("Imported: 2 · Already there: 0 · Unreadable: 0");

  await run.getByRole("link", { name: "Show these games" }).click();
  await expect(page.getByText("1–2 of 2")).toBeVisible();
  await page.getByRole("row").filter({ hasText: "Morphy, Paul" }).click();

  // The viewer starts at the starting position; the arrow keys and End step through the game.
  await expect(
    page.getByRole("heading", { name: "Morphy, Paul – Duke Karl / Count Isouard" }),
  ).toBeVisible();
  await expect(page.getByRole("img", { name: "Starting position" })).toBeVisible();
  await page.keyboard.press("ArrowRight");
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("img", { name: "Position after 1… e5" })).toBeVisible();
  await page.keyboard.press("End");
  await expect(page.getByRole("img", { name: "Position after 17. Rd8#" })).toBeVisible();

  const moves = page.getByRole("group", { name: "Moves" });
  await expect(moves).toContainText("This pins the knight");
  await expect(moves).toContainText("is the usual move.");

  // A new tag, created from the viewer.
  await page.getByRole("combobox", { name: "Add a tag" }).fill("Brilliancy");
  await page.getByRole("option", { name: "Create “Brilliancy”" }).click();
  await expect(page.getByRole("row", { name: "Brilliancy" })).toBeVisible();

  // Back in the list, the tag filter finds the game, and only that one.
  await page.getByRole("navigation").getByRole("link", { name: "Games" }).click();
  await expect(page.getByText("1–2 of 2")).toBeVisible();
  await page.getByRole("button", { name: "Any Tag" }).click();
  await page.getByRole("option", { name: "Brilliancy" }).click();
  await expect(page.getByText("1–1 of 1")).toBeVisible();
  await expect(page.getByRole("row").filter({ hasText: "Morphy, Paul" })).toBeVisible();
});
