# Pinocchio onboarding screens (approved 2026-10-21)

Approved by the owner as the target look for `npx @stiflerxd/pinocchio setup` (spec §8). Step blocks
tick off as they complete: ✔ done (green), ◉ running (yellow), ○ waiting, ✖ failed (red).
`NO_COLOR` disables colour; terminals without box-drawing glyphs fall back to `+--+` boxes.

## Banner and progress strip

```
  ██████╗ ██╗███╗   ██╗ ██████╗  ██████╗ ██████╗██╗  ██╗██╗ ██████╗
  ██╔══██╗██║████╗  ██║██╔═══██╗██╔════╝██╔════╝██║  ██║██║██╔═══██╗
  ██████╔╝██║██╔██╗ ██║██║   ██║██║     ██║     ███████║██║██║   ██║
  ██╔═══╝ ██║██║╚██╗██║██║   ██║██║     ██║     ██╔══██║██║██║   ██║
  ██║     ██║██║ ╚████║╚██████╔╝╚██████╗╚██████╗██║  ██║██║╚██████╔╝
  ╚═╝     ╚═╝╚═╝  ╚═══╝ ╚═════╝  ╚═════╝ ╚═════╝╚═╝  ╚═╝╚═╝ ╚═════╝
            🤥  Your agent's nose grows when it lies.   v0.1.0

  ┌─ Setup ───────────────────────────────────────────────────────┐
  │  ✔ 1  Check system          ◉ 2  Find tests       ○ 3  Choose │
  │  ○ 4  Review                ○ 5  Install          ○ 6  Test   │
  └───────────────────────────────────────────────────────────────┘
```

## Steps

```
  ╭─ ✔ Step 1 · Check system ─────────────────────────────────────╮
  │  ✔ Node 22.11      ✔ git 2.47      ✔ Claude Code 2.1.289       │
  │  ● Codex 0.163  → skill only (Codex has no blocking hook)      │
  ╰────────────────────────────────────────────────────────────────╯

  ╭─ ◉ Step 2 · Find your tests ──────────────────────────────────╮
  │  Looking in D:\my-app ...                                      │
  │   ✔ package.json      →  npm test                              │
  │   ✔ pyproject.toml    →  pytest                                │
  │   ─ go.mod            →  not found                             │
  │  Pinocchio will treat these as "real test runs".               │
  ╰────────────────────────────────────────────────────────────────╯

  ╭─ ◉ Step 3 · Choose ───────────────────────────────────────────╮
  │  Where to install?   ❯ This project only   All my projects     │
  │  Mode?               ❯ Default — block only when proven false  │
  │                        Report  — never block, just receipts    │
  │                        Strict  — also block when it can't tell │
  │  Commit the lie ledger to git?   ( ) yes   (●) no              │
  ╰────────────────────────────────────────────────────────────────╯

  ╭─ ◉ Step 4 · Review — nothing written yet ─────────────────────╮
  │   + plugin   pinocchio@pinocchio   (via claude plugin install) │
  │   + file     .claude/pinocchio.json          (your settings)   │
  │   + folder   .claude/pinocchio/              (ledger, ignored) │
  │   Token cost:  ~93 tokens/session · 0 for the hook itself      │
  │   Reads only:  never edits code, never runs commands for you   │
  │   Install now?  ❯ Yes    No                                    │
  ╰────────────────────────────────────────────────────────────────╯

  ╭─ ✔ Step 5 · Install ──────────────────────────────────────────╮
  │  ✔ marketplace added   ✔ plugin installed   ✔ settings saved   │
  ╰────────────────────────────────────────────────────────────────╯

  ╭─ ✔ Step 6 · Test run ─────────────────────────────────────────╮
  │  Replaying a sample session where the agent lied...            │
  │   🤥 Pinocchio · FAIL · nose +1                                │
  │   ✖ stale-tests   claimed "all tests pass", no test ran        │
  │                   after the last edit (src/cart.js)            │
  │   → agent was sent back to run the tests                       │
  ╰────────────────────────────────────────────────────────────────╯

   🎉  Pinocchio is watching.  Restart Claude Code to begin.
   pinocchio status     see your agent's nose count
   pinocchio doctor     check everything is working
   pinocchio uninstall  remove exactly what was added
```

## `pinocchio status`

```
  ╭─ 🤥 Pinocchio · D:\my-app ────────────────────────────────────╮
  │  Nose length   ▇▇▇▇▇▇░░░░  6 lies caught                       │
  │  Sessions      41 checked · 33 pass · 6 fail · 2 can't tell    │
  │  Last 3        ✔ PASS   ✖ FAIL stale-tests   ✔ PASS            │
  │  Ledger        ✔ hash chain intact (212 entries)               │
  ╰────────────────────────────────────────────────────────────────╯
```
