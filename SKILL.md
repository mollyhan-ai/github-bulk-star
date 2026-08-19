---
name: github-bulk-star
description: Preview and Star public GitHub repositories from up to six repository or user repositories-page links. Use when a user wants one confirmed batch of GitHub Stars; do not use for follows, watches, forks, or unstarring.
---

# GitHub Bulk Star

Turn up to six GitHub links into one deduplicated Star batch. A direct
`https://github.com/owner/repo` link contributes that repository. A
`https://github.com/owner?tab=repositories` link contributes only the public
repositories returned on the first API page; never paginate.

If the user supplies a plain `https://github.com/owner` profile, do not pass it
to the helper or change GitHub. Propose the exact normalized
`https://github.com/owner?tab=repositories` URL and obtain explicit user
confirmation before generating the preview. That normalization confirmation is
not permission to Star: after previewing, obtain a separate confirmation for
the exact resolved repository list.

Resolve `scripts/github_bulk_star.py` relative to this `SKILL.md` and run it by
absolute path rather than reproducing the API loop manually:

```bash
python3 /absolute/path/to/github-bulk-star/scripts/github_bulk_star.py URL [URL ...]
```

The default run is a read-only preview. Show the user the resolved repository
list and total, including any duplicates removed. Obtain one explicit
confirmation for that exact list immediately before changing GitHub. Then run:

```bash
python3 /absolute/path/to/github-bulk-star/scripts/github_bulk_star.py --execute --confirm STAR URL [URL ...]
```

The helper accepts mixed link types, skips repositories already Starred by the
authenticated account, and never removes a Star. It rejects profile links
without `tab=repositories`, deeper links such as issues or pull requests, other
hosts, and batches larger than six input links.

Execution requires a GitHub token from `GH_TOKEN` or `GITHUB_TOKEN`, or a valid
GitHub CLI login discoverable through `gh auth token`. Never print or store the
token. If authentication, expansion, or any repository operation fails, report
the partial result and stop after this single requested pass. A transient
transport failure may be retried once for that same repository because the Star
operation is idempotent; never broaden the target list or retry the whole batch
automatically.
