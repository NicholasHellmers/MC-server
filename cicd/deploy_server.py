"""CI script to trigger rolling update and restart on remote AWS server via SSH."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from typing import Any


def execute_remote_deploy(
    host: str,
    user: str = "ubuntu",
    ssh_key_path: str | None = None,
    remote_dir: str = "/opt/mc-server",
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    """Execute git pull and docker compose restart on the remote server."""
    if not host:
        return {"status": "error", "message": "Missing SERVER_HOST."}

    remote_cmd = (
        f"cd {remote_dir} && "
        "git pull origin main && "
        "docker compose restart minecraft"
    )

    ssh_args = [
        "ssh",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
    ]
    if ssh_key_path and os.path.exists(ssh_key_path):
        ssh_args.extend(["-i", ssh_key_path])

    ssh_args.extend([f"{user}@{host}", remote_cmd])

    try:
        res = subprocess.run(
            ssh_args,
            capture_output=True,
            text=True,
            check=True,
            timeout=timeout_seconds,
        )
        return {"status": "success", "stdout": res.stdout, "stderr": res.stderr}
    except subprocess.CalledProcessError as e:
        return {"status": "error", "stdout": e.stdout, "stderr": e.stderr}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def main() -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Deploy updates to remote Minecraft server.")
    parser.add_argument("--host", default=os.getenv("SERVER_HOST", ""), help="Remote server IP/hostname")
    parser.add_argument("--user", default=os.getenv("SERVER_USER", "ubuntu"), help="Remote SSH user")
    parser.add_argument("--key", default=os.getenv("SERVER_SSH_KEY_PATH", None), help="SSH private key path")
    parser.add_argument("--remote-dir", default="/opt/mc-server", help="Path to repo on remote server")
    args = parser.parse_args()

    res = execute_remote_deploy(
        host=args.host,
        user=args.user,
        ssh_key_path=args.key,
        remote_dir=args.remote_dir,
    )
    print(f"Deploy result: {res}")
    return 0 if res.get("status") == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
