# redesign/: the Kook'n redesign, ready for Codex

Built by Claude on 2026-10-06 with the owner. This folder is **local only**: its `.gitignore` hides it, so the dev
worktree stays clean for AGENTS.md's deploy script. The repo is public, so never commit this folder. Port its pieces
instead.

## Read in this order

1. `HANDOFF-CODEX.md`: what to implement, in what order, with gates, tests, AGENTS.md entries and rollback.
2. `PLAN.md`: the strategy on one page.
3. `AUDIT.md`: what the click-through, payloads and X analytics showed.
4. `proposals/RESULTS.md` and `proposals/DATA.md`: picks and pipeline proposals (shadow first), payloads, search,
   guard.
5. `social/X-PLAYBOOK.md`: profile, cards, rhythm, captions, the owner's daily routine, measurement.
6. `design/brand.md`, `design/tokens.css`, `copy/glossary.md`.

## See it

```bash
python3 -m http.server 8790 --bind 127.0.0.1 --directory ~/Projects/sports-dev
```

Then open http://localhost:8790/redesign/site/. It runs on the live site's data and falls back to the local build.

## Folders

| Folder | What |
|---|---|
| `site/` | Working prototype (`index.html`, `app.css`, `app.js`). Reuses the real `site/core.js`, `live.js` and `personal.js`. |
| `tests/` | `node --test redesign/tests/*.test.js` (19 tests: math, labels, old-link map, copy and CSS floors) |
| `brand/` | Logo vectors, plus `png/` (favicons, X avatar, X banner, lockups). Rebuild: `python3 redesign/brand/build_brand.py` |
| `social/` | Felt card templates (`cards.py`), `render_samples.py`, `samples/*.png`, `fixtures/` |
| `design/`, `copy/`, `proposals/` | Tokens, brand guide, copy deck, proposals |
