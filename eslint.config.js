// Flat config (current ESLint default). Covers apps/web (once scaffolded)
// and packages/schemas/typescript. Add `eslint-config-next` here once
// apps/web is actually stood up as a Next.js app (Thato's call).
import js from "@eslint/js";
import tseslint from "typescript-eslint";
import eslintConfigPrettier from "eslint-config-prettier";

export default [
  { ignores: ["**/node_modules/**", "**/.next/**", "**/dist/**", "**/.turbo/**", "**/.dist/**"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  eslintConfigPrettier,
  {
    files: ["apps/web/**/*.{ts,tsx}", "packages/schemas/typescript/**/*.ts"],
    languageOptions: {
      parserOptions: { ecmaVersion: "latest", sourceType: "module" },
    },
  },
];
