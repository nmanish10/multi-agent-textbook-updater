Use this folder for golden parser/rendering fixtures.

Suggested fixture set:
- one clean Markdown textbook
- one structured PDF with reliable numbering
- one messy PDF with weak headings

Each fixture can later store:
- expected chapter count
- expected section count
- expected warnings
- expected rendered Markdown snapshot

Automated regression snapshots currently live in `tests/snapshots/`.
