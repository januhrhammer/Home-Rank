<!--
The title becomes the commit message on main, so write it as a Conventional Commit:
feat(import): resume interrupted imports
-->

## Summary

<!-- What changes, in a few sentences. Link the issue, e.g. "Closes #12". -->

## Why

<!-- The problem this solves, or the reason for the approach you chose. -->

## How tested

<!-- Tests added or changed, and what you checked by hand. -->

## Screenshots

<!-- For changes to the interface; delete this section otherwise. -->

## Checklist

- [ ] `just check` passes
- [ ] Tests cover the change (a bug fix starts with a test that fails without it)
- [ ] Docs updated where behaviour or configuration changed (README, `docs/`, `.env.example`)
- [ ] Database migration included and read through, if models changed
- [ ] `just gen-api` run, if the API changed
- [ ] Breaking change for self-hosters? Then the title has a `!` and the description says what
      they must do.
