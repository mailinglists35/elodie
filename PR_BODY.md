Title: Disable automatic metadata writes by default and add --allow-metadata-writes

Summary

- Prevent Elodie from writing metadata (and creating *_original backup files) by default.
- Introduce a new explicit CLI flag `--allow-metadata-writes` to enable metadata writes when the user opts in.
- Propagate the flag through `import` and `update` flows and guard the actual write in a single place (`filesystem.process_file`).
- Add regression tests that ensure no *_original files are created by default and that backups are created when the flag is provided.

Why

Previously Elodie could write metadata and create backup files (`*_original`) implicitly during normal operations. This caused local clutter and surprised users who ran imports or updates without expecting their files to be modified. The patch makes file modifications opt-in and prevents accidental writes.

What changed

- CLI: Add `--allow-metadata-writes` to both `import` and `update` commands (default: False).
- Core: Pass `allow_metadata_writes` from CLI → `process_file` and guard `media.set_original_name` behind the flag.
- Media: Avoid creating copies/backups when metadata writes are disabled.
- Tests: Add `tests/test_fix_duplicates.py` with two tests for default and opt-in behaviors.

Testing

- Run the test suite: `pytest -q`
- Manual:
  - Default (no writes): `python elodie.py import --source /tmp/src --destination /tmp/dst` → no `*_original` files created.
  - With writes: `python elodie.py import --source /tmp/src --destination /tmp/dst --allow-metadata-writes` → `*_original` files are created.

Notes

- Backwards compatible: default behavior remains non-destructive.
- Low risk: all writes are guarded centrally and require explicit opt-in.

