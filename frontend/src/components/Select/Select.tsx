import {
  Button,
  Label,
  ListBox,
  ListBoxItem,
  Popover,
  Select as AriaSelect,
  SelectValue,
} from "react-aria-components";

import styles from "./Select.module.css";

export interface Option {
  id: string;
  name: string;
}

interface SelectProps {
  label: string;
  options: Option[];
  /** The chosen option's id; null for "anyOption". */
  value: string | null;
  onChange: (value: string | null) => void;
  /** The first entry, which stands for no choice, e.g. "Any". */
  anyOption: string;
}

const ANY = "";

/** A drop-down list with an entry for "no choice", built on React Aria's accessible Select. */
export function Select({ label, options, value, onChange, anyOption }: SelectProps) {
  return (
    <AriaSelect
      className={styles.select}
      value={value ?? ANY}
      onChange={(key) => {
        onChange(key === ANY || key === null ? null : String(key));
      }}
    >
      <Label className={styles.label}>{label}</Label>
      <Button className={styles.button}>
        <SelectValue />
        <span aria-hidden="true">▾</span>
      </Button>
      <Popover className={styles.popover}>
        <ListBox className={styles.listBox} items={[{ id: ANY, name: anyOption }, ...options]}>
          {(option) => (
            <ListBoxItem className={styles.option} id={option.id}>
              {option.name}
            </ListBoxItem>
          )}
        </ListBox>
      </Popover>
    </AriaSelect>
  );
}
