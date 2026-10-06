Kook'n redesign handoff from Claude. The owner has approved starting tonight. They're away until later and asked me to send this.

Everything is in ~/Projects/sports-dev/redesign/ on branch dev. That folder is git-ignored by its own .gitignore, so dev stays clean. Read redesign/README.md first, then all of redesign/HANDOFF-CODEX.md. AGENTS.md rules apply as always: the deploy lock and script, both test suites, rehearse.py, publication_guard.py, and commits as keenroudy22. The working prototype is redesign/site/. To preview it: python3 -m http.server 8790 --directory ~/Projects/sports-dev, then open /redesign/site/.

Scope tonight is phases C0, C1 and C2 only (HANDOFF §3):
- C0: add the dated owner rules in §8 to AGENTS.md and the status items in §9. Commit redesign/, with one exception: the owner hasn't decided whether the X analytics figures in redesign/AUDIT.md should be public. Replace redesign/.gitignore with a single line, AUDIT.md, so that file stays local, and commit everything else.
- C1: publish the prototype as a noindex preview at /sports/next/ (index.html, app.js, app.css reading ../data/ and ../core.js etc.). Add the guard allowlist entry with its test and update PUBLIC-PAYLOADS.md. /sports/ must not change.
- C2: port the parity tests (HANDOFF §5), the route tables and the record-headline check. Keep the 23 tests in redesign/tests/model.test.js passing.

Hard stops. Each of these needs the owner's explicit yes, so do not do any of them tonight:
- the C3 swap of the live site;
- the card cutover (C5);
- any results or pipeline change (R0–R7, HANDOFF §7);
- flipping OWNER_FLAGS in app.js (CLV headline, ROI);
- the R5 trends default;
- anything that posts to X or Discord, or changes posting.
If something blocks you, stop and say so here. Do not work around a gate.

When you finish, reply here with:
1. the commits and the publish-run result;
2. the preview URL, plus the 375 px and 1440 px checks (no console errors, no sideways scroll);
3. test counts for both suites;
4. answers to these questions (HANDOFF §13):
   a. Where is kookn-product-plan-2026-10-05.html, and is anything in it still pending?
   b. Why is `reasoning` null on every pick? Can build_site.py publish structured reasons[] / cautions[] again?
   c. Where do the "Book unavailable" rows and the "ESPN BET" book name come from? Can they be fixed at the source?
   d. When is a quiet window for the card cutover?
   e. Does Buffer's free queue limit (about 10 per channel) ever bind today?
   f. What is the current state of P06, P08 and P09?
   g. Can the pipeline store which side was listed at home for neutral-site games (for example `listedHome`), so team pages can sign the closing spread?
   h. Does anything in docs/product-status.json conflict with this plan?
