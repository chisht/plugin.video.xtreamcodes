#!/bin/sh
# Releases the current addon.xml version to the `kodi-repo` branch.
# Local use:      ./release.sh              (build + push, needs push access)
# What actually runs on the branch: release/executor.sh (see that file) - it
# only builds and commits, and lets the workflow push. On Actions the build
# step calls this script with UPLOAD=0.
set -e
cd "$(dirname "$0")"

if [ "${UPLOAD:-1}" = "0" ]; then
  exec python3 tools/release_repo.py --remote "$1" --branch "${BRANCH:-kodi-repo}" --no-push
fi
exec python3 tools/release_repo.py "$@"
