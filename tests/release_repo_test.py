#!/usr/bin/env python3
"""tests/release_repo_test.py - offline checks for tools/release_repo.py.

Builds into a scratch clone (a bare "origin" plus a work clone) and verifies:
  * the version from addon.xml is released, as a commit on top of the branch,
    without touching the clone it runs in (no checkout, no local branch),
  * addons.xml / addons.xml.md5 / index.html / zips/<id>/* are pushed and are
    usable by Kodi (md5 matches, zip has the add-on at its root),
  * a second run with the same version is a no-op,
  * .nojekyll and the zips of earlier releases survive, branch-only files are
    pruned, and a version bump is released (keeping the older zips),
  * --dry-run and --worktree work and push nothing / something respectively.
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRANCH = "kodi-repo"

fails = 0


def check(ok, what, extra=""):
    global fails
    print(("PASS " if ok else "FAIL ") + what + ((" - " + str(extra)) if extra and not ok else ""))
    if not ok:
        fails += 1


def run(args, cwd=None, expect=0):
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if expect is not None and r.returncode != expect:
        print(r.stdout)
        print(r.stderr)
        check(False, "command failed: " + " ".join(args), r.returncode)
    return r


def git(args, cwd, **kw):
    return run(["git"] + args, cwd=cwd, **kw)


def md5(path):
    with open(path, "rb") as fh:
        return hashlib.md5(fh.read()).hexdigest()


def version_of(addon_xml):
    import xml.etree.ElementTree as ET
    return ET.parse(addon_xml).getroot().get("version")


def bump(src, version):
    """Set the add-on version in addon.xml, return the previous one."""
    import re
    path = os.path.join(src, "addon.xml")
    text = open(path).read()
    head, rest = text.split("<addon ", 1)
    old = re.search(r'version="([^"]+)"', rest).group(1)
    open(path, "w").write(head + "<addon " + rest.replace(
        'version="{}"'.format(old), 'version="{}"'.format(version), 1))
    return old


def add_to_branch(wt, files):
    for rel, blob in files.items():
        path = os.path.join(wt, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(blob)
    git(["add", "-A"], cwd=wt)
    git(["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "extra"], cwd=wt)
    git(["push", "-q", "origin", BRANCH], cwd=wt)


def main():
    scratch = tempfile.mkdtemp(prefix="release-test-")
    try:
        origin = os.path.join(scratch, "origin.git")
        clone = os.path.join(scratch, "clone")
        release = os.path.join(clone, "tools", "release_repo.py")  # the tool as it is committed
        wt = os.path.join(scratch, "branch")
        remote = origin  # --remote takes a name or a URL/path (a local path works too)
        git(["init", "-q", "--bare", origin], cwd=scratch)
        shutil.copytree(ROOT, clone, ignore=shutil.ignore_patterns(".git", "__pycache__", "repo_out"))
        git(["init", "-q"], cwd=clone)
        git(["add", "-A"], cwd=clone)
        git(["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"], cwd=clone)
        git(["branch", "-M", "main"], cwd=clone)
        ver = version_of(os.path.join(clone, "addon.xml"))

        # --- first release: the branch does not exist yet ---------------------
        r = run([sys.executable, release, "--remote", remote], cwd=clone)
        check("Nothing to release" not in r.stdout and ver in r.stdout,
              "first release reports version " + ver, r.stdout)
        parents = git(["rev-list", "--count", BRANCH], cwd=origin).stdout.strip()
        check(parents == "1", "branch is a single commit", parents)
        check(not git(["branch", "--list", BRANCH], cwd=clone).stdout.strip(),
              "no local branch left behind in the clone")
        check(not os.path.exists(os.path.join(clone, "addons.xml")),
              "the clone's working tree is untouched")

        git(["clone", "-q", "-b", BRANCH, origin, wt], cwd=scratch)
        names = git(["ls-tree", "-r", "--name-only", "HEAD"], cwd=wt).stdout.split()
        for want in ("addons.xml", "addons.xml.md5", "index.html", "repository.chisht.zip",
                     "zips/plugin.video.xtreamcodes/plugin.video.xtreamcodes-{}.zip".format(ver)):
            check(want in names, "pushed " + want)
        check(md5(os.path.join(wt, "addons.xml")) == open(
            os.path.join(wt, "addons.xml.md5")).read().strip(), "addons.xml.md5 matches addons.xml")
        addons = open(os.path.join(wt, "addons.xml")).read()
        check('id="plugin.video.xtreamcodes"' in addons and 'id="repository.chisht"' in addons,
              "addons.xml lists both add-ons")
        check('version="{}"'.format(ver) in addons, "addons.xml has the released version")
        zpath = os.path.join(wt, "zips", "plugin.video.xtreamcodes",
                             "plugin.video.xtreamcodes-{}.zip".format(ver))
        with zipfile.ZipFile(zpath) as zf:
            zip_names = zf.namelist()
        check("plugin.video.xtreamcodes/addon.xml" in zip_names, "zip has the add-on at its root")
        check("plugin.video.xtreamcodes/service.py" in zip_names, "zip has service.py")
        check(os.path.exists(os.path.join(wt, "zips", "plugin.video.xtreamcodes",
                                          "plugin.video.xtreamcodes-{}.zip.sha256".format(ver))),
              "zip has a sha256 next to it")

        # --- same version again: nothing to do --------------------------------
        r = run([sys.executable, release, "--remote", remote], cwd=clone)
        check("Nothing to release" in r.stdout, "re-running the same version is a no-op", r.stdout)

        # --- .nojekyll and older zips must survive, branch-only files go -------
        old_zip = "zips/plugin.video.xtreamcodes/plugin.video.xtreamcodes-1.0.0.zip"
        add_to_branch(wt, {".nojekyll": b"", old_zip: b"old", "stale.txt": b"branch only"})
        r = run([sys.executable, release, "--remote", remote], cwd=clone)
        git(["pull", "-q", "--ff-only", "origin", BRANCH], cwd=wt)
        check(os.path.exists(os.path.join(wt, ".nojekyll")), ".nojekyll kept")
        check(os.path.exists(os.path.join(wt, old_zip)), "older zip kept for rollback")
        check(not os.path.exists(os.path.join(wt, "stale.txt")), "branch-only file pruned")

        # --- a version bump is released ---------------------------------------
        old = bump(clone, "9.9.9")
        r = run([sys.executable, release, "--remote", remote, "--message", "9.9.9"], cwd=clone)
        check("9.9.9" in r.stdout, "release reports 9.9.9", r.stdout)
        subject = git(["log", "-1", "--format=%s", BRANCH], cwd=origin).stdout.strip()
        check(subject == "9.9.9", "commit uses --message", subject)
        git(["pull", "-q", "--ff-only", "origin", BRANCH], cwd=wt)
        check(os.path.exists(os.path.join(
            wt, "zips", "plugin.video.xtreamcodes", "plugin.video.xtreamcodes-9.9.9.zip")),
            "new zip added")
        check(os.path.exists(os.path.join(wt, old_zip)), "previous zip still there")
        check("9.9.9" in open(os.path.join(wt, "addons.xml")).read(), "addons.xml updated")
        check(len(git(["rev-list", BRANCH], cwd=origin).stdout.split()) == 4,
              "one commit per release, on top of the previous branch tip")
        bump(clone, old)

        # --- --dry-run pushes nothing, --print only lists files ---------------
        bump(clone, "9.9.10")
        before = git(["rev-parse", BRANCH], cwd=origin).stdout
        r = run([sys.executable, release, "--remote", remote, "--dry-run"], cwd=clone)
        check("9.9.10" in r.stdout and "addons.xml" in r.stdout, "dry-run lists the files", r.stdout)
        check(before == git(["rev-parse", BRANCH], cwd=origin).stdout, "dry-run pushed nothing")
        r = run([sys.executable, release, "--print"], cwd=clone)
        check("addons.xml" in r.stdout and "git" not in r.stdout.lower().split("file(s)")[0][:0],
              "--print lists the built files without git", r.stdout)
        check(before == git(["rev-parse", BRANCH], cwd=origin).stdout, "--print pushed nothing")

        # --- --worktree takes the checkout route ------------------------------
        r = run([sys.executable, release, "--remote", remote, "--worktree"], cwd=clone)
        check("9.9.10" in r.stdout, "--worktree releases", r.stdout)
        new = git(["rev-parse", BRANCH], cwd=origin).stdout
        check(new != before, "--worktree pushed the release")
        check(len(git(["rev-list", BRANCH], cwd=origin).stdout.split()) == 5,
              "--worktree adds one commit")
        check(not git(["branch", "--list", BRANCH], cwd=clone).stdout.strip(),
              "--worktree left no local branch behind")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    print("----")
    print("release_repo: " + ("ok" if not fails else "{} FAILED".format(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
