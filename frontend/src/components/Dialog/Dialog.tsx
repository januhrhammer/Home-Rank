import type { ReactNode } from "react";
import { DialogTrigger, Modal, ModalOverlay } from "react-aria-components";

import styles from "./Dialog.module.css";

/**
 * A modal dialog opened by its trigger: it keeps the focus inside, closes with Escape, and
 * tells screen readers. The content is a React Aria Dialog; `dialogStyles` has the classes
 * for it, its form and its buttons.
 */
export function ModalDialog({ trigger, children }: { trigger: ReactNode; children: ReactNode }) {
  return (
    <DialogTrigger>
      {trigger}
      <ModalOverlay className={styles.overlay} isDismissable>
        <Modal className={styles.modal}>{children}</Modal>
      </ModalOverlay>
    </DialogTrigger>
  );
}

export { styles as dialogStyles };
