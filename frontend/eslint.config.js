// ESLint finds bugs, React and hook mistakes, accessibility problems and unsorted imports.
// Formatting is Prettier's job.
import js from "@eslint/js";
import eslintReact from "@eslint-react/eslint-plugin";
import prettier from "eslint-config-prettier/flat";
import jsxA11y from "eslint-plugin-jsx-a11y-x";
import reactHooks from "eslint-plugin-react-hooks";
import simpleImportSort from "eslint-plugin-simple-import-sort";
import { defineConfig } from "eslint/config";
import globals from "globals";
import tseslint from "typescript-eslint";

export default defineConfig(
  { ignores: ["dist"] },
  {
    files: ["**/*.{ts,tsx}"],
    extends: [
      js.configs.recommended,
      tseslint.configs.strictTypeChecked,
      eslintReact.configs["strict-type-checked"],
      reactHooks.configs.flat.recommended,
      jsxA11y.configs.strict,
    ],
    languageOptions: {
      globals: globals.browser,
      parserOptions: {
        // The type-checked rules get their type information from tsconfig.json.
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    plugins: { "simple-import-sort": simpleImportSort },
    rules: {
      "simple-import-sort/imports": "error",
      "simple-import-sort/exports": "error",
      // @eslint-react has its own copies of these official React hooks rules. Keep the React
      // team's originals (react-hooks/...) so each problem is reported once.
      "@eslint-react/error-boundaries": "off",
      "@eslint-react/exhaustive-deps": "off",
      "@eslint-react/purity": "off",
      "@eslint-react/rules-of-hooks": "off",
      "@eslint-react/set-state-in-effect": "off",
      "@eslint-react/set-state-in-render": "off",
      "@eslint-react/static-components": "off",
      "@eslint-react/unsupported-syntax": "off",
      "@eslint-react/use-memo": "off",
    },
  },
  // Last: switches off all rules that would conflict with Prettier's formatting.
  prettier,
);
