#!/bin/sh
# Release executor: the only job allowed to write to the protected `kodi-repo`
# branch. Runs on the repo's default branch (job re-uses this commit), builds
# the repository files and pushes them to the branch.
#
#   sh release/executor.sh            # build + push origin/kodi-repo
#   sh release/executor.sh --dry-run  # build, show the changes, push nothing
set -e
cd "$(dirname "$0")/.."
exec python3 tools/release_repo.py --push "$@"
