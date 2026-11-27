#!/bin/sh
# Builds the Kodi repository and pushes it to the `kodi-repo` branch.
# Run after bumping the version in addon.xml. Kodi picks the update up
# on its next repository check (or Add-ons > ... > Check for updates).
set -e
cd "$(dirname "$0")"
src=$(pwd)
branch=kodi-repo
wt=$(mktemp -d)
trap 'cd "$src"; git worktree remove --force "$wt" >/dev/null 2>&1 || true; rm -rf "$wt"' EXIT

git fetch origin "+refs/heads/$branch:refs/remotes/origin/$branch" 2>/dev/null || true
if git rev-parse --verify -q "origin/$branch" >/dev/null; then
  git worktree add -q -B "$branch" "$wt" "origin/$branch"
else
  git worktree add -q --detach "$wt"
  (cd "$wt" && git checkout -q --orphan "$branch" && git rm -rqf .)
fi

python3 tools/build_repo.py "$wt"
cd "$wt"
git add -A
if git diff --cached --quiet; then
  echo "Nothing changed; did you bump the version in addon.xml?"
  exit 0
fi
ver=$(python3 -c "import xml.etree.ElementTree as E; print(E.parse('$src/addon.xml').getroot().get('version'))")
git commit -qm "Publish plugin.video.xtreamcodes $ver"
git push -u origin "$branch"
