#!/usr/bin/env python3
"""
Commit generated data files and push them to the repository.

    python3 scripts/publish.py "commit message" data/a.json data/b.json

Each attempt starts from the latest remote commit and writes our freshly
generated files on top ("last writer wins"), so two workflows finishing at
the same moment can never leave a rebase conflict behind. If every attempt is
rejected the script exits with an error, so the run shows up red in the
Actions tab instead of silently losing the update.
"""
import os
import subprocess
import sys
import time

BRANCH = os.environ.get("GITHUB_REF_NAME") or "main"
BOT_NAME = "market-dashboard-bot"
BOT_EMAIL = "actions@users.noreply.github.com"


def git(*args, check=True):
    res = subprocess.run(["git", *args], capture_output=True, text=True)
    if check and res.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {res.stderr.strip()[:400]}")
    return res


def publish(files, message, attempts=6):
    files = [f for f in files if os.path.exists(f)]
    if not files:
        print("Nothing to publish (no output files were produced).", file=sys.stderr)
        return "nothing"
    contents = {}
    for f in files:
        with open(f, "rb") as fh:
            contents[f] = fh.read()
    git("config", "user.name", BOT_NAME)
    git("config", "user.email", BOT_EMAIL)
    for attempt in range(1, attempts + 1):
        try:
            git("fetch", "--quiet", "origin", BRANCH)
            git("reset", "--quiet", "--hard", f"origin/{BRANCH}")
            for f, data in contents.items():
                with open(f, "wb") as fh:
                    fh.write(data)
            git("add", "--", *files)
            if git("diff", "--cached", "--quiet", check=False).returncode == 0:
                print("No changes to commit.", file=sys.stderr)
                return "unchanged"
            git("commit", "--quiet", "-m", message)
            if git("push", "--quiet", "origin", f"HEAD:{BRANCH}", check=False).returncode == 0:
                print(f"Pushed: {', '.join(files)}", file=sys.stderr)
                return "pushed"
            print(f"Push attempt {attempt} was rejected (the branch moved on) - retrying.", file=sys.stderr)
        except RuntimeError as e:
            print(f"Attempt {attempt}: {e}", file=sys.stderr)
        time.sleep(2 + 3 * attempt)
    raise SystemExit(f"ERROR: could not push {', '.join(files)} after {attempts} attempts.")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit('usage: publish.py "commit message" file [file ...]')
    publish(sys.argv[2:], sys.argv[1])
