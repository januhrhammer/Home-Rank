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
  "nav.label": "Main",
  "nav.import": "Import",
  "import.title": "Import games",
  "import.intro":
    "Upload a PGN file with your games. Games you already have are skipped, so you can upload a whole export again to add the new ones.",
  "import.drop": "Drop a PGN file here, or",
  "import.choose": "choose a file",
  "import.uploading": "Uploading {name}…",
  "import.wrongType": "Only PGN files (.pgn) can be imported.",
  "import.tooLarge": "This file is larger than the server accepts.",
  "import.uploadFailed": "The upload didn't work. Please try again.",
  "import.history": "Your imports",
  "import.none": "No imports yet.",
  "import.loadFailed": "Your imports couldn't be loaded.",
  "import.status.queued": "Waiting to start",
  "import.status.running": "Importing",
  "import.status.done": "Done",
  "import.status.failed": "Stopped",
  "import.progress": "Progress of {name}",
  "import.counts": "Imported: {imported} · Already there: {duplicates} · Unreadable: {failed}",
  "import.problems": "Problems ({count})",
  "import.problemAtLine": "Line {line}: {reason}",
} as const;

export type MessageKey = keyof typeof messages;

const numbers = new Intl.NumberFormat();

/**
 * The text for a key. Placeholders such as {count} are filled in from `values`; numbers are
 * written the reader's way, e.g. "1,045" or "1.045".
 */
export function t(key: MessageKey, values: Record<string, string | number> = {}): string {
  let text: string = messages[key];
  for (const [name, value] of Object.entries(values)) {
    text = text.replaceAll(`{${name}}`, typeof value === "number" ? numbers.format(value) : value);
  }
  return text;
}
