# Contributing

Thanks for helping improve Skylander Character Editor.

## Before opening an issue

Include:
- Operating system and version
- App version or Git commit
- Whether the dump is initialized or unused (if known)
- Figure name, game generation, and figure type (if known)
- Exact steps and error message

Do **not** upload someone else's `.sky`/NFC dump or any dump you do not have permission to share. Remove personal information from logs.

## Changes to the binary format logic

- Keep original files unchanged in tests; use temporary copies.
- Add tests for parsing and post-write validation.
- Do not claim a generation/figure is supported solely because the file is 1,024 bytes.
- Never extend fresh-save initialization to a new generation without before/after dumps from the same figure and successful in-game validation.
- Document known limitations and update the compatibility section.

## Development

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
```
