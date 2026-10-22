/**
 * All UI text goes through t(), so the app can be translated later without touching every
 * component. English only for now.
 *
 * TypeScript checks the keys: t("app.nmae") is a type error.
 */
const messages = {
  "app.name": "Home-Rank",
  "app.tagline": "Your games, analysed overnight, turned into your personal training plan.",
  "footer.sourceCode": "Source code",
  "notFound.title": "Page not found",
  "notFound.backHome": "Back to the start page",
} as const;

export type MessageKey = keyof typeof messages;

export function t(key: MessageKey): string {
  return messages[key];
}
