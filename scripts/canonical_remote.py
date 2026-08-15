#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Canonical form of a git remote URL, and its digest.

    python3 scripts/canonical_remote.py --digest <url>
    python3 scripts/canonical_remote.py <url>

Why this exists
---------------
The push guard compared remote URLs as strings. Cross-review (agy, P0)
pointed out that the same destination has many spellings, and that this made
the deny-list decorative:

    https://host.example.com/owner/repo.git
    https://host.example.com/owner/repo
    https://host.example.com/owner/repo.git/
    git@host.example.com:owner/repo.git
    ssh://git@host.example.com/owner/repo
    https://user@HOST.EXAMPLE.COM/Owner/Repo.git

All six reach the same repository. Under a string comparison, five of them slip
past a deny-list entry written for the sixth, and — worse in the other
direction — a developer using the ssh spelling of the *allowed* remote is
rejected for no reason.

Canonicalization is deliberately lossy and lower-cases the path. On the hosts
this guards, owner and repository names are case-insensitive; treating them as
case-sensitive would mean `Owner/Repo` and `owner/repo` hash differently, and
the deny-list would miss one of them. Erring toward collapsing spellings is the
fail-closed direction for a deny-list.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys

SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*://", re.I)
SCP_LIKE = re.compile(r"^(?:([^@/]+)@)?([^:/]+):(?!//)(.+)$")


def canonical(url: str) -> str:
    """host/path, lower-cased, with scheme, userinfo, .git and trailing / removed."""
    u = url.strip()
    if not u:
        return ""
    m = SCP_LIKE.match(u) if not SCHEME.match(u) else None
    if m:                                  # git@host:owner/repo.git
        u = f"{m.group(2)}/{m.group(3)}"
    else:
        u = SCHEME.sub("", u)
        if "@" in u.split("/", 1)[0]:      # userinfo@host/...
            u = u.split("@", 1)[1]
    u = u.rstrip("/")
    if u.endswith(".git"):
        u = u[: -len(".git")]
    u = u.rstrip("/")
    return u.lower()


def digest(url: str) -> str:
    return hashlib.sha256(canonical(url).encode()).hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="canonical git remote URL")
    ap.add_argument("url")
    ap.add_argument("--digest", action="store_true")
    a = ap.parse_args(sys.argv[1:] if argv is None else argv)
    c = canonical(a.url)
    if not c:
        print("canonical-remote: empty URL", file=sys.stderr)
        return 2
    print(digest(a.url) if a.digest else c)
    return 0


if __name__ == "__main__":
    sys.exit(main())
