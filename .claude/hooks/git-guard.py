#!/usr/bin/env python3
"""PreToolUse(Bash) guard — deterministic enforcement of CLAUDE.md git HARD RULEs.

Converts prose rules the model must remember into a harness-level block:
  - HARD RULE 1/3: no direct push to a protected branch (develop / main).
  - HARD RULE 4: no force-push to a protected branch; no `git push --no-verify`.
  - PR base=main is Mode 3 deploy territory (git-publisher agent + deploy keyword).

ALLOWS: feature/* pushes, `gh pr merge --admin`, everything non-git.

Design: FAIL-OPEN. Any parse/exec error -> exit 0 (allow). A guard that breaks
the session is worse than no guard; GitHub server-side branch protection is the
real backstop, this is a fast local pre-flight. Blocks via exit code 2 (stderr
shown to Claude) — the canonical PreToolUse deny mechanism.
"""
import sys
import json
import re
import subprocess

PROTECTED = ("develop", "main")


def deny(reason):
    sys.stderr.write("BLOCKED by git-guard hook: " + reason + "\n")
    sys.exit(2)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    cmd = ((data.get("tool_input") or {}).get("command") or "")
    # fast path — only git push / gh pr create are interesting
    if "git push" not in cmd and "gh pr create" not in cmd:
        sys.exit(0)

    # inspect each &&/||/;/| -separated sub-command
    for part in re.split(r"&&|\|\||;|\|", cmd):
        p = part.strip()

        if p.startswith("git push"):
            toks = p.split()
            if "--no-verify" in toks:
                deny("`git push --no-verify` skips the migration pre-push hook "
                     "(CLAUDE.md HARD RULE 4). Remove --no-verify.")

            forced = any(
                t in ("--force", "-f") or t == "--force-with-lease"
                or t.startswith("--force-with-lease=")
                for t in toks
            )

            refspecs = [t for t in toks[2:] if not t.startswith("-")]
            targets_protected = False
            for t in refspecs:
                dst = t.split(":")[-1]                 # dst side of a refspec
                if t.startswith("+") or dst.startswith("+"):
                    forced = True                      # `+ref` is git's force shorthand
                dst = dst.lstrip("+")
                leaf = dst.rsplit("/", 1)[-1]          # final path component
                if dst in PROTECTED or leaf in PROTECTED:
                    targets_protected = True

            # bare `git push` (no explicit refspec) -> check current branch
            if not refspecs or all(s in ("origin", "upstream") for s in refspecs):
                try:
                    br = subprocess.run(
                        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                        capture_output=True, text=True, timeout=2,
                    ).stdout.strip()
                    if br in PROTECTED:
                        targets_protected = True
                except Exception:
                    pass

            if targets_protected and forced:
                deny("force-push to a protected branch (develop/main) is the "
                     "post-deploy carve-out only — git-publisher Mode 3 "
                     "(CLAUDE.md HARD RULE 4).")
            elif targets_protected:
                deny("direct push to a protected branch (develop/main). Push "
                     "from feature/* and merge via PR; the git-publish skill "
                     "handles feature->develop (CLAUDE.md HARD RULE 1/3).")

        elif p.startswith("gh pr create"):
            # base=main is Mode 3 deploy territory. The ONLY sanctioned base=main
            # PR is the deploy PR `--base main --head develop` (git-publisher.md) —
            # carve it out so the guard does not break the deploy workflow.
            if re.search(r"--base[=\s]+main\b", p) and not re.search(r"--head[=\s]+develop\b", p):
                deny("PR base=main from a non-develop head is Mode 3 deploy "
                     "territory — git-publisher agent + explicit deploy keyword. "
                     "(base=main + head=develop, the sanctioned deploy PR, is allowed.)")

    sys.exit(0)


if __name__ == "__main__":
    main()
