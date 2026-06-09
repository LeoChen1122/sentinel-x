"""kubectl command policy for sandbox (default deny)."""

from __future__ import annotations

_FORBIDDEN_SUBSTRINGS = (
    "delete namespace",
    "--all-namespaces",
    " -A ",
    " exec ",
    " run ",
    " apply ",
    " create ",
    " patch ",
    " replace ",
)


def namespace_allowed(namespace: str, allowed: str) -> bool:
    return namespace.strip() == allowed.strip()


def validate_kubectl_argv(argv: list[str], *, allowed_namespace: str) -> tuple[bool, str]:
    """Return (ok, reason). argv includes kubectl as argv[0]."""
    if not argv or argv[0] != "kubectl":
        return False, "command must start with kubectl"

    joined = " ".join(argv).lower()
    for bad in _FORBIDDEN_SUBSTRINGS:
        if bad.strip() in joined:
            return False, f"forbidden pattern: {bad.strip()!r}"

    if "--all" in argv or "-A" in argv:
        return False, "all-namespaces not allowed"

    ns = _extract_namespace(argv)
    if ns is None:
        return False, "missing -n/--namespace"
    if not namespace_allowed(ns, allowed_namespace):
        return False, f"namespace {ns!r} not in allowlist ({allowed_namespace!r})"

    subcmd = argv[1] if len(argv) > 1 else ""
    if subcmd == "delete" and len(argv) > 2 and argv[2] == "namespace":
        return False, "delete namespace not allowed"

    allowed_verbs = frozenset({"get", "describe", "delete", "scale", "rollout"})
    if subcmd not in allowed_verbs:
        return False, f"subcommand {subcmd!r} not allowed"

    if subcmd == "delete" and (len(argv) < 4 or argv[2] != "pod"):
        return False, "only delete pod is allowed"

    return True, "ok"


def _extract_namespace(argv: list[str]) -> str | None:
    for i, part in enumerate(argv):
        if part in ("-n", "--namespace") and i + 1 < len(argv):
            return argv[i + 1]
    return None
