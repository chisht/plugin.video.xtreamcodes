#!/bin/sh
# Create or update the ruleset that protects the `kodi-repo` branch, using the
# gh CLI (needs admin rights on the repository). Safe to re-run.
#
#   sh release/ruleset.sh            # create it from release/ruleset.json
#   sh release/ruleset.sh --show     # print the rulesets that exist
#
# The bypass list in release/ruleset.json is "Repository admin" (actor_id 5).
# If your own account is the admin you push the release with, use
# release/ruleset-token.json instead (same, but the release is pushed with the
# RELEASE_TOKEN secret instead of a bypass).
set -e
cd "$(dirname "$0")"
repo=$(git config --get remote.origin.url | sed -E 's#(git@|https://)github.com[:/]##; s#\.git$##')

if [ "$1" = "--show" ]; then
  gh api "repos/$repo/rulesets" --jq '.[] | "\(.id)\t\(.name)\t\(.target)"'
  exit 0
fi

id=$(gh api "repos/$repo/rulesets" --jq ".[] | select(.name==\"kodi-repo\") | .id" 2>/dev/null || true)
if [ -n "$id" ]; then
  gh api -X PUT "repos/$repo/rulesets/$id" --input ruleset.json >/dev/null
  echo "updated ruleset kodi-repo ($id)"
else
  gh api -X POST "repos/$repo/rulesets" --input ruleset.json >/dev/null
  echo "created ruleset kodi-repo"
fi
gh api "repos/$repo/rulesets" --jq '.[] | select(.name=="kodi-repo") | ._links.html' 2>/dev/null || true
