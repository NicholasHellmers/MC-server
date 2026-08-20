"""Tests for mod_migrator module."""

import hashlib
from pathlib import Path
from unittest.mock import patch

from mc_server_tools.mod_migrator import (
    calculate_hashes,
    classify_mod_side,
    clean_mod_slug,
    generate_pw_toml_content,
    main,
    scan_and_migrate_mods,
)


def test_classify_mod_side():
    assert classify_mod_side("Sodium-fabric-0.8.12.jar") == "client"
    assert classify_mod_side("Iris-fabric-1.8.14.jar") == "client"
    assert classify_mod_side("c2me-fabric-mc1.21.1.jar") == "server"
    assert classify_mod_side("lithium-fabric-0.15.4.jar") == "server"
    assert classify_mod_side("Cobblemon-fabric-1.7.3.jar") == "both"


def test_calculate_hashes(tmp_path: Path):
    test_file = tmp_path / "sample.jar"
    test_file.write_bytes(b"dummy jar content for testing")
    hashes = calculate_hashes(test_file)
    assert hashes["sha1"] == hashlib.sha1(b"dummy jar content for testing").hexdigest()
    assert hashes["sha256"] == hashlib.sha256(b"dummy jar content for testing").hexdigest()
    assert hashes["sha512"] == hashlib.sha512(b"dummy jar content for testing").hexdigest()


def test_clean_mod_slug():
    assert clean_mod_slug("Cobblemon-fabric-1.7.3+1.21.1.jar") == "cobblemon"
    assert clean_mod_slug("Waystones-fabric-1.21.1-21.1.37.jar.disabled") == "waystones"
    assert clean_mod_slug("some_mod_v1.0.jar") == "some_mod"
    assert clean_mod_slug("---.jar") == "mod"


def test_generate_pw_toml_content():
    content = generate_pw_toml_content(
        name="testmod",
        filename="testmod-1.0.jar",
        side="both",
        sha1_hash="abc",
        sha512_hash="def12345678901234567890",
        download_url="https://example.com/mod.jar",
    )
    assert 'name = "testmod"' in content
    assert 'url = "https://example.com/mod.jar"' in content
    assert 'side = "both"' in content

    content_no_url = generate_pw_toml_content(
        name="testmod",
        filename="testmod-1.0.jar",
        side="client",
        sha1_hash="abc",
        sha512_hash="def12345678901234567890",
    )
    assert 'side = "client"' in content_no_url
    assert "url =" not in content_no_url


def test_scan_and_migrate_mods(tmp_path: Path):
    src = tmp_path / "source_mods"
    src.mkdir()
    target = tmp_path / "target_server"

    # Test with non-existent dir
    res_empty = scan_and_migrate_mods(tmp_path / "nonexistent", target)
    assert res_empty == []

    # Create dummy jars
    (src / "Cobblemon-fabric-1.7.3.jar").write_bytes(b"cobblemon content")
    (src / "Cobblemon-fabric-1.7.4.jar").write_bytes(b"cobblemon v2 content")  # tests duplicate slug handling
    (src / "Sodium-fabric-0.8.jar").write_bytes(b"sodium content")

    migrated = scan_and_migrate_mods(src, target)
    assert len(migrated) == 3
    assert (target / "pack.toml").exists()
    assert (target / "index.toml").exists()
    assert (target / "mods" / "cobblemon.pw.toml").exists()
    assert (target / "mods" / "cobblemon-1.pw.toml").exists()
    assert (target / "mods" / "sodium.pw.toml").exists()


def test_main(tmp_path: Path):
    src = tmp_path / "source_mods"
    src.mkdir()
    (src / "mod1.jar").write_bytes(b"content")
    target = tmp_path / "server"

    with patch("sys.argv", ["mod_migrator", "--source", str(src), "--target", str(target)]):
        ret = main()
        assert ret == 0
