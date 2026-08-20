"""CI script to validate Packwiz index and export .mrpack for GitHub Releases."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mc_server_tools.modpack_builder import ModpackBuilder


def run_build(
    server_dir: Path | str = "server",
    output_mrpack: Path | str = "Cobblemon-Modpack.mrpack",
) -> int:
    """Validate modpack and export .mrpack archive."""
    builder = ModpackBuilder(server_dir=server_dir)

    print("Step 1: Refreshing index hashes...")
    refresh_res = builder.refresh_index()
    print(f"Refresh status: {refresh_res}")

    print("Step 2: Validating modpack manifest...")
    val_res = builder.validate_manifest()
    if not val_res.get("valid"):
        print(f"ERROR: Modpack validation failed: {val_res.get('errors')}", file=sys.stderr)
        return 1

    print(
        f"Validation passed: {val_res['total_mods']} total mods "
        f"({val_res['client_only_mods']} client, {val_res['server_only_mods']} server, {val_res['shared_mods']} shared)."
    )

    print(f"Step 3: Exporting .mrpack to '{output_mrpack}'...")
    exported_file = builder.export_mrpack(output_path=output_mrpack)
    print(f"SUCCESS: Exported {exported_file} ({exported_file.stat().st_size} bytes).")
    return 0


def main() -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Build and export Modrinth .mrpack bundle.")
    parser.add_argument("--server-dir", default="server", help="Server directory path")
    parser.add_argument("--output", default="Cobblemon-Modpack.mrpack", help="Output .mrpack file path")
    args = parser.parse_args()
    return run_build(server_dir=args.server_dir, output_mrpack=args.output)


if __name__ == "__main__":
    sys.exit(main())
