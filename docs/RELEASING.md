# Releasing (the `kodi-repo` branch)

Kodi devices get updates from the **`kodi-repo` branch** of this repository:
the `repository.chisht` add-on points at its `addons.xml`, `addons.xml.md5` and
`zips/`, and Kodi downloads `zips/<id>/<id>-<version>.zip` from there
(see `repository.chisht/addon.xml`).

That branch is **protected** (repository ruleset *kodi-repo*): nobody pushes to
it by hand, and the only thing that writes to it is the **Release to kodi-repo**
workflow.

## Releasing a new version

1. Bump `version` in `addon.xml` and add a line to the `<news>` changelog.
2. Commit and merge to the default branch (`main`).
3. Actions → **Release to kodi-repo** → *Run workflow*.
   * always releases the default branch's commit, whatever you pick in the
     dialog, so the released code is the reviewed code;
   * `dry_run = true` builds and lists the files without pushing;
   * the workflow runs `python3 tests/release_repo_test.py` first, then
     `sh release/executor.sh`, which builds the repository files
     (`tools/release_repo.py` + `tools/build_repo.py`) and pushes one commit.

Kodi picks the new version up on its next repository check (or
*Add-ons → … → Check for updates*). Old zips stay on the branch, so a device
that is behind can still install an older version.

Locally the same thing is `./release.sh` (see `publish_repo.sh` for the old
name); it needs push access to `kodi-repo`, which the protection takes away
from humans on purpose. `./release.sh --print` only builds and lists the files,
`./release.sh --dry-run` shows the commit that would be pushed.

## The protection and the workflow's credentials

The ruleset (`kodi-repo`, admins can bypass) makes the branch:
delete-protected, non-fast-forward push blocked, and blocks direct pushes for
everyone but the revision runner and the ruleset's bypass list.

Pushing from the workflow needs one of these (in order of preference):

1. **`GITHUB_TOKEN` with the ruleset bypass** – add **GitHub Actions** to the
   ruleset's bypass list (Settings → Rules → *kodi-repo* → Bypass list → *Add
   bypass* → search for "GitHub Actions" and pick the app). The workflow then
   pushes with its own token and no secret is needed:
   `.github/workflows/release.yml` sets `permissions: contents: write`, and
   `GITHUB_TOKEN` in the *Release* step is used as the git credential by
   Actions, so nothing else is needed.
2. **A fine-grained personal access token** in the repo secret `RELEASE_TOKEN`
   (Contents: **Read and write**), when the bypass list does not offer GitHub
   Actions (e.g. it only offers roles/teams). The workflow checks out with it
   and Actions then uses it for the push as well. Add the token's owner to the
   ruleset bypass list if the push is still refused, and rotate the token when
   it expires.

If the *Release* step fails with

```
Changes must be made through a pull request / protected branch hook declined
```

then the push from Actions is not allowed yet: add the bypass (1.) or the
token (2.). Nothing is half-released when that happens — the commit is only
pushed at the end — so simply fix the permission and run the workflow again.

## What the release writes

```
addons.xml            both add-ons, one <addon> block each
addons.xml.md5        md5 of addons.xml (Kodi checks it)
index.html            a link to repository.chisht.zip (GitHub Pages friendly)
repository.chisht.zip stable name, for the first install
zips/<id>/<id>-<version>.zip (+ .sha256, icon.png, fanart.jpg)
```

`zips/` and `.nojekyll` are kept from the branch; everything else that is not
part of the build is removed, so the branch always mirrors `addon.xml`.
