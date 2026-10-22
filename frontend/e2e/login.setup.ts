import { expect, test } from "@playwright/test";

import { AUTH_FILE, PASSWORD, USERNAME } from "./account";

test("log in", async ({ page }) => {
  await page.goto("/games");
  // Not logged in yet: the app asks for the account first.
  await expect(page.getByRole("heading", { name: "Log in" })).toBeVisible();

  await page.getByLabel("Username").fill(USERNAME);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Log in" }).click();

  // ... and then goes on to the page we wanted.
  await expect(page.getByRole("heading", { name: "Your games" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Log out" })).toBeVisible();

  await page.context().storageState({ path: AUTH_FILE });
});
