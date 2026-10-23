import { expect, test } from "@playwright/test";

// A phone's screen (an iPhone 14's, in CSS pixels): no page may be wider than that, or the
// whole page scrolls sideways.
const PHONE_WIDTH = 390;
test.use({ viewport: { width: PHONE_WIDTH, height: 844 } });

const PAGES = [
  "/",
  "/games",
  "/train",
  "/repertoires",
  "/search", // has a board, whose coordinates once stuck out
  "/reference",
  "/labels",
  "/import",
  "/settings",
];

for (const address of PAGES) {
  test(`${address} fits a phone's width`, async ({ page }) => {
    await page.goto(address);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await page.waitForLoadState("networkidle"); // the rest of the page, e.g. a board

    // As a string: these tests' TypeScript knows no browser globals.
    const width = await page.evaluate<number>("document.documentElement.scrollWidth");
    expect(width).toBeLessThanOrEqual(PHONE_WIDTH);
  });
}

test("the pages are behind the menu button on a phone", async ({ page }) => {
  await page.goto("/");
  const train = page.getByRole("link", { name: "Train" });
  await expect(train).toBeHidden();

  await page.getByRole("button", { name: "Menu" }).click();
  await train.click();

  await expect(page).toHaveURL(/\/train$/);
  await expect(train).toBeHidden();
});
