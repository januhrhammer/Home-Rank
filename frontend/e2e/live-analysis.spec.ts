import { expect, test } from "@playwright/test";

// Live analysis in the real app (ADR 0018): the page is cross-origin isolated, the server
// serves Stockfish's files with the header they need, and the engine reports its lines.
test("live analysis runs Stockfish in the browser, on several threads", async ({ page }) => {
  await page.goto("/search");
  expect(await page.evaluate<boolean>("crossOriginIsolated")).toBe(true);

  await page.getByText("Live analysis").click();

  const panel = page.getByRole("region", { name: "Live analysis" });
  await expect(panel.getByText(/^Depth \d+$/)).toBeVisible({ timeout: 15_000 });
  await expect(panel.getByRole("listitem")).toHaveCount(3);
  await expect(panel.getByRole("listitem").first()).toContainText(/^[+−]\d+\.\d\d/);
});
