#!/usr/bin/env python3
"""Inspect the current repo's origin remote and emit one of:

    product | canonical | personal | unknown

Detection rules (in order):
  1. URL matches https://github.com/canonical/<repo>      -> canonical or product
  2. URL matches https://github.com/<other-org>/<repo>:
     a. If the repo is a fork of canonical/<repo> (detected via
        `gh repo view --json isFork,parent`, or an `upstream` remote
        pointing at canonical/<repo>)                     -> canonical or product
     b. Otherwise                                          -> personal
  3. No remote / no clear org                              -> unknown

The fork lookup matters because Charm Tech engineers routinely work
from a personal fork of a canonical/* repo; the baseline that applies
is the upstream repo's, not the fork owner's.

Product-tier classification within canonical/ is driven by a small
allowlist below (Charm Tech products as of 2026-06 — operator, pebble,
jubilant, concierge, charmlibs). All other canonical/* repos are
'canonical' tier (cross-cutting requirements only).

Override: pass an argument to force a tier (useful when auditing a
repo before transfer to the canonical org).

Exit 0 always; the tier name is printed on stdout.
"""

from __future__ import annotations

import shutil
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from lib.common import origin_url, run  # noqa: E402


PRODUCT_REPOS = {"operator", "pebble", "jubilant", "concierge", "charmlibs"}


def main() -> int:
    if len(sys.argv) >= 2:
        arg = sys.argv[1]
        if arg in ("product", "canonical", "personal"):
            print(arg)
            return 0
        print("unknown", file=sys.stderr)
        return 1

    url = origin_url()
    if not url:
        print("unknown")
        return 0

    prefix = "https://github.com/"
    if not url.startswith(prefix):
        # Some other forwarding host; don't guess.
        print("unknown")
        return 0

    path = url[len(prefix):]
    parts = path.split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        print("unknown")
        return 0
    org, repo = parts

    # If origin is not under canonical/, the repo may still be a fork of
    # a canonical/* repo — in which case the upstream's baseline applies.
    if org != "canonical":
        parent_slug = ""
        if shutil.which("gh"):
            result = run([
                "gh", "repo", "view", f"{org}/{repo}",
                "--json", "isFork,parent",
                "--jq",
                r'select(.isFork) | .parent'
                r' | select(.owner.login == "canonical")'
                r' | "\(.owner.login)/\(.name)"',
            ])
            parent_slug = result.stdout.strip()
        if not parent_slug:
            upstream = run(["git", "config", "--get", "remote.upstream.url"]).stdout.strip()
            if upstream.startswith("git@github.com:"):
                upstream = "https://github.com/" + upstream[len("git@github.com:"):]
            if upstream.endswith(".git"):
                upstream = upstream[:-4]
            if upstream.startswith(prefix):
                upstream_path = upstream[len(prefix):]
                if upstream_path.startswith("canonical/"):
                    parent_slug = upstream_path
        if parent_slug:
            org = "canonical"
            repo = parent_slug[len("canonical/"):]

    if org == "canonical":
        print("product" if repo in PRODUCT_REPOS else "canonical")
    else:
        print("personal")
    return 0


if __name__ == "__main__":
    sys.exit(main())
