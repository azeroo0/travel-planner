---
paths:
  # Scoped to what we own. `design-system/**` would also pull in the vendored
  # obsidian-mcp-server clone — ~220 files of an abandoned codebase these rules
  # say nothing useful about. `paths` has no negation, so narrow instead.
  - "plugin/**/*.{ts,tsx}"
  - "design-system/src/**/*.{ts,tsx}"
  - "design-system/.storybook/*.{ts,tsx}"
---

# TypeScript

`plugin/tsconfig.json` already enforces `strict`, `noUncheckedIndexedAccess`,
`noImplicitOverride` and `exactOptionalPropertyTypes`. Don't restate what the
compiler checks — run `pnpm typecheck`.

- No `any`. Use `unknown` plus a narrowing check.
- Annotate exported signatures. Leave local inference alone; `const n = 5` does
  not need `: number`.
- Handle errors at a declared boundary, not at every `await`. `AgentHarness.run`
  is one such boundary: it catches once and distinguishes an aborted signal
  (`cancelled`) from a real failure (`failed`). A `try/catch` around an inner
  `await` that cannot act on the error swallows that distinction, and a Stop the
  user pressed surfaces as a red error row.
- Never report a cancellation as an error.
- `src/ui` may not import the harness engine, providers, tools or `obsidian`, and
  LangChain may not appear outside `src/harness`. `pnpm boundaries` fails on
  either — see `.dependency-cruiser.cjs`.
