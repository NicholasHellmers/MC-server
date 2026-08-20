"""Module for migrating raw JAR files into Packwiz metadata format."""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path
from typing import Any

CLIENT_ONLY_PATTERNS = [
    r"advancementplaques",
    r"betterf1",
    r"betterf3",
    r"betterthirdperson",
    r"controlling",
    r"continuity",
    r"customsplashscreen",
    r"defaultoptions",
    r"entity_model_features",
    r"entity_texture_features",
    r"entityculling",
    r"fancymenu",
    r"highlight",
    r"immediatelyfast",
    r"infinite-music",
    r"iris",
    r"konkrete",
    r"melody",
    r"modmenu",
    r"moreculling",
    r"mousetweaks",
    r"musicnotification",
    r"notenoughanimations",
    r"notenoughcrashes",
    r"paginatedadvancements",
    r"particle_core",
    r"particlerain",
    r"particular",
    r"reeses-sodium-options",
    r"respackopts",
    r"sodium",
    r"sound-physics-remastered",
    r"soundsbegone",
    r"tooltipfix",
    r"xaerominimap",
    r"xaeroworldmap",
    r"zoomify",
    r"badoptimizations",
]

SERVER_ONLY_PATTERNS = [
    r"c2me",
    r"krypton",
    r"lithium",
    r"ferritecore",
    r"spark",
    r"chunky",
    r"stackdeobfuscator",
]


def classify_mod_side(filename: str) -> str:
    """Classify whether a mod should run on client, server, or both."""
    lower_name = filename.lower()
    for pattern in CLIENT_ONLY_PATTERNS:
        if re.search(pattern, lower_name):
            return "client"
    for pattern in SERVER_ONLY_PATTERNS:
        if re.search(pattern, lower_name):
            return "server"
    return "both"


def calculate_hashes(file_path: Path) -> dict[str, str]:
    """Calculate sha1, sha256, and sha512 hashes for a file."""
    sha1 = hashlib.sha1()
    sha256 = hashlib.sha256()
    sha512 = hashlib.sha512()

    with file_path.open("rb") as f:
        while chunk := f.read(65536):
            sha1.update(chunk)
            sha256.update(chunk)
            sha512.update(chunk)

    return {
        "sha1": sha1.hexdigest(),
        "sha256": sha256.hexdigest(),
        "sha512": sha512.hexdigest(),
    }


def clean_mod_slug(filename: str) -> str:
    """Derive a clean, URL-safe slug from a mod JAR filename."""
    name = filename.removesuffix(".jar").removesuffix(".disabled")
    name = re.sub(r"[-_](?:fabric|forge|neoforge|quilt).*$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"[-_]v?\d.*$", "", name)
    name = re.sub(r"[^a-zA-Z0-9_-]", "-", name).strip("-").lower()
    return name or "mod"


def generate_pw_toml_content(
    name: str,
    filename: str,
    side: str,
    sha1_hash: str,
    sha512_hash: str,
    download_url: str = "",
) -> str:
    """Generate the TOML string content for a Packwiz .pw.toml file."""
    url_line = f'url = "{download_url}"\n' if download_url else ""
    return f"""name = "{name}"
filename = "{filename}"
side = "{side}"

[download]
hash-format = "sha1"
hash = "{sha1_hash}"
{url_line}
[update]
[update.modrinth]
mod-id = "{name.lower()}"
version = "{sha512_hash[:16]}"
"""


def scan_and_migrate_mods(
    source_mods_dir: Path | str,
    target_server_dir: Path | str,
) -> list[dict[str, Any]]:
    """Scan raw JAR files and create Packwiz metadata in target server directory."""
    src_path = Path(source_mods_dir)
    target_path = Path(target_server_dir)
    target_mods = target_path / "mods"
    target_mods.mkdir(parents=True, exist_ok=True)

    migrated_mods: list[dict[str, Any]] = []
    if not src_path.is_dir():
        return migrated_mods

    jar_files = sorted(src_path.glob("*.jar"))
    index_files: list[dict[str, str]] = []

    for jar_file in jar_files:
        filename = jar_file.name
        slug = clean_mod_slug(filename)
        side = classify_mod_side(filename)
        hashes = calculate_hashes(jar_file)

        # Generate unique pw.toml filename if duplicate slug
        pw_filename = f"{slug}.pw.toml"
        pw_file_path = target_mods / pw_filename
        counter = 1
        while pw_file_path.exists():
            pw_filename = f"{slug}-{counter}.pw.toml"
            pw_file_path = target_mods / pw_filename
            counter += 1

        content = generate_pw_toml_content(
            name=slug,
            filename=filename,
            side=side,
            sha1_hash=hashes["sha1"],
            sha512_hash=hashes["sha512"],
        )
        pw_file_path.write_text(content, encoding="utf-8")

        pw_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        index_files.append({
            "file": f"mods/{pw_filename}",
            "hash": pw_hash,
        })

        migrated_mods.append({
            "name": slug,
            "filename": filename,
            "side": side,
            "pw_file": str(pw_file_path),
        })

    # Write index.toml
    index_content = 'hash-format = "sha256"\n\n'
    for item in index_files:
        index_content += f'[[files]]\nfile = "{item["file"]}"\nhash = "{item["hash"]}"\nmetafile = true\n\n'

    index_path = target_path / "index.toml"
    index_path.write_text(index_content, encoding="utf-8")
    index_hash = hashlib.sha256(index_content.encode("utf-8")).hexdigest()

    # Write pack.toml
    pack_content = f"""name = "Cobblemon Adventure"
author = "Cobbleverse Team"
version = "1.0.0"
description = "Cobblemon 1.21.1 Fabric Modpack Single Source of Truth"

[index]
file = "index.toml"
hash-format = "sha256"
hash = "{index_hash}"

[versions]
fabric = "0.19.3"
minecraft = "1.21.1"
"""
    (target_path / "pack.toml").write_text(pack_content, encoding="utf-8")

    return migrated_mods


def main() -> int:
    """CLI entrypoint for mod migration."""
    parser = argparse.ArgumentParser(description="Migrate raw JAR mods into Packwiz metadata.")
    parser.add_argument("--source", default="Cobblemon Server/mods", help="Source folder with JARs")
    parser.add_argument("--target", default="server", help="Target server folder")
    args = parser.parse_args()

    mods = scan_and_migrate_mods(args.source, args.target)
    print(f"Successfully migrated {len(mods)} mods into Packwiz structure in '{args.target}'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
