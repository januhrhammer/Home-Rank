import { ApiError } from "../../api/errors";
import { t } from "../../lib/i18n";

/**
 * What to tell the user when a change failed: the server's own explanation when it gave one
 * (a name already taken, a move that isn't legal, a file too large), else a general message.
 */
export function errorMessage(error: Error): string {
  return error instanceof ApiError && error.detail !== undefined
    ? error.detail
    : t("repertoire.failed");
}
