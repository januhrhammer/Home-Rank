import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

// axe (https://github.com/dequelabs/axe-core) checks each page for what a program can find:
// contrast, names and roles, labels, headings, landmarks. Keyboard paths and what screen
// readers announce still need people; see the unit tests and docs/development.md.
// With games in the database, moves written with figurines (♘f3, named "Nf3" for screen
// readers) would trip "label-content-name-mismatch": on purpose, so exclude them then.
const RULES = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"];

const PAGES = [
  "/",
  "/games",
  "/train",
  "/repertoires",
  "/search",
  "/reference",
  "/labels",
  "/import",
  "/settings",
];

for (const colorScheme of ["light", "dark"] as const) {
  test.describe(`${colorScheme} theme`, () => {
    test.use({ colorScheme });

    for (const address of PAGES) {
      test(`${address} passes axe's checks`, async ({ page }) => {
        await page.goto(address);
        await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
        await page.waitForLoadState("networkidle"); // the rest of the page, e.g. a board

        const results = await new AxeBuilder({ page }).withTags(RULES).analyze();
        expect(results.violations).toEqual([]);
      });
    }
  });
}
