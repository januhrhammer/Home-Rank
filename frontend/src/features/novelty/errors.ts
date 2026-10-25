import { ApiError } from "../../api/errors";
import { t } from "../../lib/i18n";

/** What to tell the user when a change failed: the server's own explanation when it gave one
 * (a search still running, a position that can't be searched), else a general message. */
export function errorMessage(error: Error): string {
  return error instanceof ApiError && error.detail !== undefined
    ? error.detail
    : t("novelty.failed");
}
