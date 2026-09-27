---
paths:
  # Both forms on purpose: whether `**` also matches zero path segments differs
  # between glob implementations, and `plugin/src/main.ts` — where the lifecycle
  # invariants below matter most — sits directly in `src/`.
  - "plugin/src/*.{ts,tsx}"
  - "plugin/src/**/*.{ts,tsx}"
---

# Plugin invariants

Product rules that no tool catches. Changing one of these means changing
`docs/ARCHITECTURE.md` first, not the code.

- `onload` stays cheap: no indexing, no model call, no vault scan. Defer that to
  `onLayoutReady`. `onunload` gives back everything it registered — but does not
  detach leaves, which Obsidian restores itself after an update.
- Terminal run states (`complete`, `incomplete`, `cancelled`, `failed`) are not
  loading states. No state disables input. The composer is always present; Stop
  takes over the send slot inside it rather than replacing it.
- Tool activity stays a separate event. It never becomes assistant prose, and it
  appears once per call.
- Nothing is written to the vault without a preview the user approved. Insertion
  is an application action, not a model tool.

The UI, harness and LangChain boundaries are enforced by `pnpm boundaries` and
are deliberately not repeated here.
