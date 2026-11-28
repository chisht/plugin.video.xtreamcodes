#!/usr/bin/env python3
"""Release the add-on to the Kodi repository branch (`kodi-repo`).

Builds the repository files from `addon.xml`, syncs them into the repository
branch and pushes the result. `.github/workflows/release.yml` (Actions >
Release to kodi-repo) runs this through `release/executor.sh` and is the only
thing that should write to `kodi-repo` once the branch is protected.

    python3 tools/release_repo.py                  # build + push origin/kodi-repo
    python3 tools/release_repo.py --dry-run        # build + show the changes only
    python3 tools/release_repo.py --print          # build + list the files, no git
    python3 tools/release_repo.py --remote <name>  # another remote of this repo
    python3 tools/release_repo.py --branch foo     # another repository branch
    python3 tools/release_repo.py --worktree       # push a checkout instead of one commit

The build itself is `tools/build_repo.py`: it writes `addons.xml`,
`addons.xml.md5`, `index.html`, `zips/<id>/<id>-<version>.zip` (+ `.sha256`,
icon, fanart) and the stable `repository.chisht.zip`. Zips that are already on
the branch are kept, so users can still roll back to an older version;
everything else that is not part of the build is removed (except `.nojekyll`).

By default the branch gets a single commit with the branch's current tip as
its parent, built with git plumbing: no checkout, no working tree and no local
branch, so it cannot disturb the clone it runs in.
"""
import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.dont_write_bytecode = True
import build_repo  # noqa: E402  (path set above)

DEFAULT_BRANCH = "kodi-repo"
DEFAULT_REMOTE = "origin"
KEEP = {".nojekyll"}  # not built, but must survive on the branch
KEEP_DIRS = ("zips/",)  # released zips of older versions: kept, so users can roll back
BOT = ("github-actions[bot]", "41898282+github-actions[bot]@users.noreply.github.com")


def git(args, env=None, check=True):
    environment = dict(os.environ)
    environment.update(env or {})
    result = subprocess.run(["git", "-C", ROOT] + args, capture_output=True, text=True,
                            env=environment)
    if check and result.returncode:
        sys.exit("git {} failed:\n{}{}".format(" ".join(args), result.stdout, result.stderr))
    return result.stdout.strip()


def version():
    import xml.etree.ElementTree as ET
    return ET.parse(os.path.join(ROOT, "addon.xml")).getroot().get("version")


def build(outdir):
    build_repo.main(outdir)
    return outdir


def walk(outdir):
    """relative path -> (absolute path, mode)"""
    out = {}
    for dirpath, dirnames, filenames in os.walk(outdir):
        dirnames[:] = sorted(dirnames)
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, outdir).replace(os.sep, "/")
            mode = "100755" if os.access(full, os.X_OK) else "100644"
            out[rel] = (full, mode)
    return out


def blob(path, env):
    return git(["hash-object", "-w", "--", path], env=env).strip()


def index_entries(env):
    """path -> sha from the temporary index."""
    out = {}
    for line in git(["ls-files", "-s", "--full-name"], env=env).splitlines():
        meta, path = line.split("\t", 1)
        mode, sha, _ = meta.split()
        out[path] = sha
    return out


def fetch_base(branch, remote):
    """Fetch refs/heads/<branch> into refs/remotes/release/<branch>, return its sha."""
    ref = "refs/remotes/release/" + branch
    git(["fetch", "--quiet", remote, "+refs/heads/{0}:{1}".format(branch, ref)], check=False)
    return git(["rev-parse", "--verify", "--quiet", ref], check=False)


def plumbing_commit(files, branch, remote, message):
    """Commit `files` (path -> abs path) on top of the branch tip; return (sha, tip)."""
    index = tempfile.mktemp(prefix="release-index-")
    env = {"GIT_INDEX_FILE": index}
    try:
        tip = fetch_base(branch, remote)
        if tip:
            git(["read-tree", tip], env=env)  # keeps .nojekyll etc.
        else:
            git(["read-tree", "--empty"], env=env)
        old = index_entries(env)
        new_trees = {}
        for rel, (path, mode) in sorted(files.items()):
            sha = blob(path, env)
            git(["update-index", "--add", "--cacheinfo", "{},{},{}".format(mode, sha, rel)], env=env)
            new_trees[rel] = sha
        for rel in old:
            if rel not in files and rel not in KEEP and not rel.startswith(KEEP_DIRS):
                git(["update-index", "--force-remove", "--", rel], env=env)
        tree = git(["write-tree"], env=env)
        if tip and git(["rev-parse", "{}^{{tree}}".format(tip)], check=False) == tree:
            return None, tip
        parents = [tip] if tip else []
        args = ["commit-tree", tree]
        for parent in parents:
            args += ["-p", parent]
        sha = git(["-c", "user.name=" + BOT[0], "-c", "user.email=" + BOT[1]] + args
                  + ["-m", message], env=env)
        return sha, tip
    finally:
        if os.path.exists(index):
            os.remove(index)


def push_worktree(files, branch, remote, dry_run, message):
    """--worktree: drop files into a real checkout of the branch and push it."""
    wt = tempfile.mkdtemp(prefix="release-branch-")
    try:
        git(["worktree", "prune"], check=False)
        tip = fetch_base(branch, remote)
        if tip:
            git(["worktree", "add", "-q", "--detach", wt, tip])
        else:
            git(["worktree", "add", "-q", "--detach", wt])
            git(["-C", wt, "rm", "-rqf", ".", "--ignore-unmatch"], check=False)
        for name in os.listdir(wt):
            if name == ".git" or name in KEEP:  # a worktree's .git is a file: keep it
                continue
            path = os.path.join(wt, name)
            shutil.rmtree(path) if os.path.isdir(path) else os.remove(path)
        for rel in sorted(files):
            dst = os.path.join(wt, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(files[rel][0], dst)
        git(["-C", wt, "add", "-A"])
        if not git(["-C", wt, "status", "--short"]):
            return None
        git(["-C", wt, "-c", "user.name=" + BOT[0], "-c", "user.email=" + BOT[1],
             "commit", "-qm", message])
        print(git(["-C", wt, "show", "--stat", "--oneline", "HEAD"]))
        if dry_run:
            return "dry-run"
        git(["-C", wt, "push", "-q", remote, "HEAD:refs/heads/" + branch])
        return "pushed"
    finally:
        git(["worktree", "remove", "--force", wt], check=False)
        shutil.rmtree(wt, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--branch", default=DEFAULT_BRANCH)
    ap.add_argument("--remote", default=DEFAULT_REMOTE, help="remote name or URL")
    ap.add_argument("--message", help="commit subject (default: Release <id> <version>)")
    ap.add_argument("--push", dest="push", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--no-push", dest="push", action="store_false", help=argparse.SUPPRESS)
    ap.add_argument("--print", dest="show", action="store_true",
                    help="build and list the files instead of touching git")
    ap.add_argument("--dry-run", action="store_true",
                    help="build and show what would change, push nothing")
    ap.add_argument("--worktree", action="store_true",
                    help="push from a real checkout of the branch")
    args = ap.parse_args()

    message = (args.message or "Release {} {}".format(
        list(build_repo.ADDONS)[0], version())).strip()
    outdir = tempfile.mkdtemp(prefix="release-out-")
    try:
        build(outdir)
        files = walk(outdir)
        if args.show:
            for rel in sorted(files):
                print(rel)
            print("{} file(s), version {}".format(len(files), version()))
            return
        if args.worktree:
            result = push_worktree(files, args.branch, args.remote, args.dry_run, message)
            if result is None:
                print("Nothing to release: version {} is already on {}".format(version(), args.branch))
            elif result == "pushed":
                print("released version {} to {}".format(version(), args.branch))
            return
        sha, tip = plumbing_commit(files, args.branch, args.remote, message)
        if sha is None:
            print("Nothing to release: version {} is already on {}".format(version(), args.branch))
            return
        if args.dry_run:
            print("version {} would be released on {} ({} commit)".format(
                version(), args.branch, "new" if not tip else "1 new"))
            if tip:
                print(git(["diff", "--stat", tip, sha]))
            for rel in sorted(files):
                print("  " + rel)
            return
        git(["push", args.remote, "{}:refs/heads/{}".format(sha, args.branch)])
        print("released version {} to {} ({})".format(version(), args.branch, sha[:8]))
    finally:
        shutil.rmtree(outdir, ignore_errors=True)


if __name__ == "__main__":
    main()
