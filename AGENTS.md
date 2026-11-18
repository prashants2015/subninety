# AGENTS.md — subninety

**Read `AGENTS.shared.md` first:** the rules for every one of the founder's repos ("ship it", tests before every PR, how we work, no secrets, no health data in logs, copy law, add-only migrations, handoff, plain English). It is a copy of the master in `prashants2015/nutrition-companion`: never edit it here (the verify command fails if you do); change the master and run `node scripts/sync-shared-rules.mjs`. This file adds the rules for this repo only, for every coding agent (Claude Code and Codex alike). `CLAUDE.md` imports both.

**Verify command:** `npm run verify`. Run it before every pull request and paste the result. It checks `AGENTS.shared.md`, then builds the site (Astro).
