import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

// A game against Maia in the real app: the model and onnxruntime in the image, the bot's
// answer in the same request, and the game saved to the user's games.
test("play a move against Maia, resign, and save the game", async ({ page }) => {
  await page.goto("/play");
  await page.getByRole("button", { name: "New game" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("textbox", { name: "Rating" })).toHaveValue("1500");
  await dialog.getByRole("button", { name: "Start" }).click();

  await expect(page.getByRole("heading", { name: "You against Maia 1500" })).toBeVisible();
  await page.getByRole("textbox", { name: "Type your move" }).fill("e4");
  await page.keyboard.press("Enter");

  // Maia answers at once: two moves in the list, and it's the user's move again.
  const moves = page.getByRole("list", { name: "Moves" });
  await expect(moves.getByRole("listitem")).toHaveCount(2);
  await expect(page.getByRole("status")).toHaveText("Your move.");

  // The game page with moves on it passes axe's checks too (see accessibility.spec.ts).
  // React Aria's live region is left out: for a few seconds it still holds the dialog's
  // announcement, which points at the dialog's title, gone since the dialog closed.
  const axe = await new AxeBuilder({ page })
    .exclude("[data-live-announcer]")
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"])
    .analyze();
  expect(axe.violations).toEqual([]);

  await page.getByRole("button", { name: "Resign" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Resign" }).click();
  await expect(page.getByRole("status")).toHaveText("You lost by resignation.");

  await page.getByRole("button", { name: "Save to my games" }).click();
  await page.getByRole("link", { name: "Open it in your games" }).click();
  await expect(page.getByRole("heading", { name: /Maia 1500/ })).toBeVisible();
});
