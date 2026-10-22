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
  "board.label": "Chess board",
  "header.logIn": "Log in",
  "header.logOut": "Log out",
  "errors.loadFailed": "This page couldn't be loaded. Please try again later.",
  "login.title": "Log in",
  "login.username": "Username",
  "login.password": "Password",
  "login.submit": "Log in",
  "login.invalidCredentials": "Wrong username or password.",
  "login.tooManyAttempts": "Too many failed attempts. Please wait a few minutes and try again.",
  "login.failed": "Logging in didn't work. Please try again.",
  "notFound.title": "Page not found",
  "notFound.backHome": "Back to the start page",
} as const;

export type MessageKey = keyof typeof messages;

export function t(key: MessageKey): string {
  return messages[key];
}
