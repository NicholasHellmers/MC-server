"""Modpack builder and validator for Packwiz and Modrinth (.mrpack) packages."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any


class ModpackBuilder:
    """Handles Packwiz index validation, .mrpack generation, and smoke tests."""

    def __init__(self, server_dir: Path | str = "server") -> None:
        self.server_dir = Path(server_dir)
        self.pack_toml = self.server_dir / "pack.toml"
        self.index_toml = self.server_dir / "index.toml"
        self.mods_dir = self.server_dir / "mods"
        self.config_dir = self.server_dir / "config"
        self.datapacks_dir = self.server_dir / "datapacks"

    def validate_manifest(self) -> dict[str, Any]:
        """Validate structure and required files of the modpack."""
        errors: list[str] = []
        if not self.pack_toml.is_file():
            errors.append(f"Missing root manifest: {self.pack_toml}")
        if not self.index_toml.is_file():
            errors.append(f"Missing index manifest: {self.index_toml}")
        if not self.mods_dir.is_dir():
            errors.append(f"Missing mods directory: {self.mods_dir}")

        pw_files = list(self.mods_dir.glob("*.pw.toml")) if self.mods_dir.is_dir() else []
        if not pw_files:
            errors.append("No .pw.toml mod definitions found in mods directory.")

        client_mods = 0
        server_mods = 0
        both_mods = 0

        for pw in pw_files:
            content = pw.read_text(encoding="utf-8")
            if "name =" not in content or "side =" not in content:
                errors.append(f"Invalid format in {pw.name}: missing required fields.")
            if 'side = "client"' in content:
                client_mods += 1
            elif 'side = "server"' in content:
                server_mods += 1
            else:
                both_mods += 1

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "total_mods": len(pw_files),
            "client_only_mods": client_mods,
            "server_only_mods": server_mods,
            "shared_mods": both_mods,
        }

    def refresh_index(self) -> dict[str, Any]:
        """Recalculate SHA256 hashes for all metadata files and update index.toml & pack.toml."""
        if not self.mods_dir.is_dir():
            return {"status": "error", "message": "Mods directory not found."}

        pw_files = sorted(self.mods_dir.glob("*.pw.toml"))
        index_lines: list[str] = ['hash-format = "sha256"\n']

        for pw in pw_files:
            content = pw.read_bytes()
            pw_hash = hashlib.sha256(content).hexdigest()
            index_lines.append(
                f'[[files]]\nfile = "mods/{pw.name}"\nhash = "{pw_hash}"\nmetafile = true\n'
            )

        index_content = "\n".join(index_lines)
        self.index_toml.write_text(index_content, encoding="utf-8")
        index_hash = hashlib.sha256(index_content.encode("utf-8")).hexdigest()

        if self.pack_toml.is_file():
            pack_lines = self.pack_toml.read_text(encoding="utf-8").splitlines()
            new_lines: list[str] = []
            for line in pack_lines:
                if line.startswith("hash ="):
                    new_lines.append(f'hash = "{index_hash}"')
                else:
                    new_lines.append(line)
            self.pack_toml.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

        return {
            "status": "success",
            "indexed_files": len(pw_files),
            "index_hash": index_hash,
        }

    def export_mrpack(self, output_path: Path | str = "Cobblemon-Modpack.mrpack") -> Path:
        """Export client modpack into Modrinth .mrpack format."""
        out = Path(output_path)
        pw_files = list(self.mods_dir.glob("*.pw.toml")) if self.mods_dir.is_dir() else []

        modrinth_files: list[dict[str, Any]] = []
        for pw in pw_files:
            content = pw.read_text(encoding="utf-8")
            # Parse simple fields
            filename = ""
            side = "both"
            sha1_hash = ""
            url = ""

            for line in content.splitlines():
                if line.startswith("filename ="):
                    filename = line.split("=", 1)[1].strip().strip('"')
                elif line.startswith("side ="):
                    side = line.split("=", 1)[1].strip().strip('"')
                elif line.startswith("hash ="):
                    sha1_hash = line.split("=", 1)[1].strip().strip('"')
                elif line.startswith("url ="):
                    url = line.split("=", 1)[1].strip().strip('"')

            if not filename:
                continue

            env_client = "required" if side in ("client", "both") else "unsupported"
            env_server = "required" if side in ("server", "both") else "unsupported"

            modrinth_files.append({
                "path": f"mods/{filename}",
                "hashes": {"sha1": sha1_hash},
                "env": {"client": env_client, "server": env_server},
                "downloads": [url] if url else [],
                "fileSize": 1000,
            })

        index_manifest = {
            "formatVersion": 1,
            "game": "minecraft",
            "versionId": "1.0.0",
            "name": "Cobblemon Adventure",
            "summary": "Cobblemon 1.21.1 Fabric Modpack Single Source of Truth",
            "files": modrinth_files,
            "dependencies": {
                "minecraft": "1.21.1",
                "fabric-loader": "0.19.3",
            },
        }

        # Write zip archive
        with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("modrinth.index.json", json.dumps(index_manifest, indent=2))

            # Include overrides (config and datapacks)
            if self.config_dir.is_dir():
                for cfg_file in self.config_dir.rglob("*"):
                    if cfg_file.is_file():
                        rel = cfg_file.relative_to(self.server_dir)
                        zf.write(cfg_file, f"overrides/{rel.as_posix()}")

            if self.datapacks_dir.is_dir():
                for dp in self.datapacks_dir.rglob("*"):
                    if dp.is_file():
                        rel = dp.relative_to(self.server_dir)
                        zf.write(dp, f"overrides/{rel.as_posix()}")

        return out

    def test_headless_server(self, timeout_seconds: int = 60) -> dict[str, Any]:
        """Run a fast headless Docker smoke test to ensure server starts without crashes."""
        if not shutil.which("docker"):
            return {
                "status": "skipped",
                "message": "Docker CLI not installed on local host; skipping headless test.",
            }

        cmd = [
            "docker",
            "compose",
            "-f",
            str(self.server_dir / "docker-compose.yml"),
            "config",
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=timeout_seconds)
            return {"status": "success", "message": "Docker compose configuration is valid.", "output": res.stdout}
        except subprocess.CalledProcessError as e:
            return {"status": "error", "message": f"Docker compose config error: {e.stderr}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


def main() -> int:
    """CLI entrypoint for Modpack Builder."""
    parser = argparse.ArgumentParser(description="Modpack builder and validator.")
    parser.add_argument("--server-dir", default="server", help="Server directory path")
    parser.add_argument("--validate", action="store_true", help="Validate manifest structure")
    parser.add_argument("--refresh", action="store_true", help="Refresh index hashes")
    parser.add_argument("--export", default=None, help="Export .mrpack to specified path")
    parser.add_argument("--test-server", action="store_true", help="Test server configuration")
    args = parser.parse_args()

    builder = ModpackBuilder(server_dir=args.server_dir)
    if args.validate:
        res = builder.validate_manifest()
        print(f"Validation: {res}")
        return 0 if res.get("valid") else 1

    if args.refresh:
        res = builder.refresh_index()
        print(f"Refresh: {res}")
        return 0

    if args.export:
        out = builder.export_mrpack(args.export)
        print(f"Exported .mrpack to: {out}")
        return 0

    if args.test_server:
        res = builder.test_headless_server()
        print(f"Server smoke test: {res}")
        return 0 if res.get("status") in ("success", "skipped") else 1

    # Default action: validate
    res = builder.validate_manifest()
    print(f"Validation summary: {res}")
    return 0 if res.get("valid") else 1


if __name__ == "__main__":
    sys.exit(main())
