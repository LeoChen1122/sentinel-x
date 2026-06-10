"""Docker-backed kubectl execution for sandbox."""

from __future__ import annotations

import subprocess
from typing import Any, Callable

from sandbox.audit import append_audit_line, new_run_id, utc_now_iso
from sandbox.config import SandboxConfig
from sandbox.policy import validate_kubectl_argv

RunSubprocess = Callable[..., subprocess.CompletedProcess[str]]


def _default_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, **kwargs)


def run_sandbox_command(
    argv: list[str],
    *,
    cfg: SandboxConfig,
    audit_meta: dict[str, Any],
    run_subprocess: RunSubprocess | None = None,
) -> dict[str, Any]:
    """Execute argv in sandbox container; append audit; return run record dict."""
    run_fn = run_subprocess or _default_run
    run_id = new_run_id()
    base_record: dict[str, Any] = {
        "run_id": run_id,
        "ts": utc_now_iso(),
        "command": argv,
        "blocked": False,
        **audit_meta,
    }

    ok_policy, policy_reason = validate_kubectl_argv(argv, allowed_namespace=cfg.namespace)
    if not ok_policy:
        base_record["blocked"] = True
        base_record["status"] = "blocked"
        base_record["message"] = policy_reason
        base_record["exit_code"] = -1
        base_record["stdout"] = ""
        base_record["stderr"] = policy_reason
        path = append_audit_line(cfg.audit_dir, base_record)
        base_record["audit_path"] = str(path)
        return base_record

    if not cfg.kubeconfig.is_file():
        base_record["status"] = "failed"
        base_record["message"] = f"kubeconfig not found: {cfg.kubeconfig}"
        base_record["exit_code"] = -1
        base_record["stdout"] = ""
        base_record["stderr"] = base_record["message"]
        path = append_audit_line(cfg.audit_dir, base_record)
        base_record["audit_path"] = str(path)
        return base_record

    kubectl_args = argv[1:]
    docker_cmd = [
        "docker",
        "run",
        "--rm",
        "--read-only",
        # Host kubeconfig (e.g. k3s.yaml) is often mode 600 root:root; non-root cannot read the bind mount.
        "--user",
        "0:0",
        "--network",
        "host",
        "-v",
        f"{cfg.kubeconfig}:/kube/config:ro",
        "-e",
        "KUBECONFIG=/kube/config",
        cfg.image,
        *kubectl_args,
    ]

    try:
        proc = run_fn(
            docker_cmd,
            capture_output=True,
            text=True,
            timeout=cfg.timeout_sec,
            check=False,
        )
        exit_code = int(proc.returncode)
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
    except subprocess.TimeoutExpired:
        exit_code = 124
        stdout = ""
        stderr = f"timeout after {cfg.timeout_sec}s"
    except FileNotFoundError as exc:
        exit_code = -1
        stdout = ""
        stderr = str(exc)

    status = "ok" if exit_code == 0 else "failed"
    base_record.update(
        {
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
            "status": status,
            "message": stderr[:500] if exit_code != 0 else "ok",
            "docker_command": docker_cmd,
        }
    )
    path = append_audit_line(cfg.audit_dir, base_record)
    base_record["audit_path"] = str(path)
    return base_record
