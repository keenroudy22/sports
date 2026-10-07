# Public website boundary

The Pages upload is the complete `site/` folder. Hiding a field or tab is not access control.
`scripts/publication_guard.py` now checks that exact folder after generation and before upload; it performs no
network calls and changes nothing. New file families require a reviewed allowlist update and fixtures.

## Reviewed public families

| Family | Public purpose |
|---|---|
| Site HTML, CSS, JavaScript and approved brand assets | The application itself, including the lazily loaded `app-more.js`; contains no authenticated premium boundary. |
| `kookn-mark.png` | 512-pixel ticket-mark avatar for the existing Discord publisher; `kookn.jpg` remains the legacy card asset. |
| `kookn-chef.png` | Owner-supplied clay-chef publisher avatar as of October 7; the server retains the ticket mark and immutable legacy attachments stay unchanged. |
| Dated NFL/CFB trend `-part-N.json` files | Complete player/stat groups split at one megabyte and loaded through the existing trend index. No threshold rows are omitted. |
| `data/research.json`, `forecasts.json`, scoreboards | Published selections, original forecasts, corrections and honest performance evidence. Preserve them. |
| Schedule, sports, line catalog, histories, identities, depth and research context | Existing public factual research and provenance; commercial permissions remain in SOURCE-RIGHTS.md. |
| `data/desk-notes.json` | Already-validated, bounded homepage research notes. Not the private operating desk. |
| `data/app/` reviewed routes | Derived page data with projections, histories, quotes, sample and freshness information. This includes the full `record.json`, the small `lines.json` manifest with `lines-NFL.json` and `lines-CFB.json`, dated NFL/CFB trend shards plus their index, and the separate CFB defense table. |
| `data/feed.xml`, `data/cards/`, `img/` | Approved public feed and artwork. Do not rewrite published images merely for a new look. |

The check rejects unknown paths, symlinks, known owner-only files, credential-bearing JSON fields and selected
recognizable token/webhook patterns. It reports only file paths and reason codes, never matched values. Private
health/reliability, live pilot state, raw posting logs, keys and unreviewed policy exports do not belong in `site/`.

This narrow guard is not a complete secret scanner, an image-content inspector, a license clearance, or a promise
that existing published research/model outputs are proprietary. It deliberately does not delete provenance or
change stored records. Future premium fields need a reviewed server-side entitlement boundary; do not add a hidden
public JSON file and call it paid access. No accounts, billing, feed expansion or data removal is authorized here.
