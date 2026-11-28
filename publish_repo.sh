#!/bin/sh
# (old name) Release the add-on to the `kodi-repo` branch.
# The build lives in tools/release_repo.py now, used by release.sh, by
# release/executor.sh (GitHub Actions) and locally:
#
#   ./release.sh                 build the current addon.xml version and push it
#   ./release.sh --dry-run       show what would change, push nothing
#   ./release.sh --print         just build and list the repository files
#
# Only use it locally if you can push to kodi-repo; on Actions the branch is
# protected and the release workflow is the way in (docs/RELEASING.md).
set -e
cd "$(dirname "$0")"
exec python3 tools/release_repo.py "$@"
