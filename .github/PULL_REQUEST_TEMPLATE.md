## What does this PR do?

<!-- Brief summary of the change and why it's needed -->

## Related issues

<!-- Link any issues this closes, e.g. "Closes #12" -->

## Quality gates

- [ ] `python -m ruff check shortube tests` — clean
- [ ] `python -m pytest` — all pass
- [ ] `python -m compileall -q shortube` — clean
- [ ] `npx tsc --noEmit` (in `remotion/`) — clean
- [ ] Offscreen `MainWindow()` boot check passes

## Notes for reviewers

<!-- Anything unusual, design decisions, or areas to focus on -->
