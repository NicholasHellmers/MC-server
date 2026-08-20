"""Tests for modpack_builder module."""

import subprocess
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from mc_server_tools.modpack_builder import ModpackBuilder, main


def test_validate_manifest_missing_files(tmp_path: Path):
    builder = ModpackBuilder(server_dir=tmp_path / "empty_server")
    res = builder.validate_manifest()
    assert res["valid"] is False
    assert len(res["errors"]) >= 3


def test_validate_manifest_success_and_side_counts(tmp_path: Path):
    server = tmp_path / "server"
    server.mkdir()
    (server / "pack.toml").write_text("name = 'test'\n", encoding="utf-8")
    (server / "index.toml").write_text("hash-format = 'sha256'\n", encoding="utf-8")
    mods = server / "mods"
    mods.mkdir()

    (mods / "client_mod.pw.toml").write_text('name = "cm"\nfilename = "cm.jar"\nside = "client"\n', encoding="utf-8")
    (mods / "server_mod.pw.toml").write_text('name = "sm"\nfilename = "sm.jar"\nside = "server"\n', encoding="utf-8")
    (mods / "both_mod.pw.toml").write_text('name = "bm"\nfilename = "bm.jar"\nside = "both"\n', encoding="utf-8")
    (mods / "invalid_mod.pw.toml").write_text('corrupt = true\n', encoding="utf-8")

    builder = ModpackBuilder(server_dir=server)
    res = builder.validate_manifest()
    assert res["valid"] is False  # due to invalid_mod
    assert res["total_mods"] == 4
    assert res["client_only_mods"] == 1
    assert res["server_only_mods"] == 1
    assert res["shared_mods"] == 2


def test_refresh_index(tmp_path: Path):
    server = tmp_path / "server"
    builder_empty = ModpackBuilder(server_dir=server)
    assert builder_empty.refresh_index()["status"] == "error"

    server.mkdir()
    mods = server / "mods"
    mods.mkdir()
    (mods / "mod1.pw.toml").write_text('name = "m1"\n', encoding="utf-8")

    # Test refresh when pack.toml does not exist
    builder_no_pack = ModpackBuilder(server_dir=server)
    res_no_pack = builder_no_pack.refresh_index()
    assert res_no_pack["status"] == "success"

    # Test refresh when pack.toml exists
    (server / "pack.toml").write_text("name = 'test'\nhash = 'old'\n", encoding="utf-8")
    builder = ModpackBuilder(server_dir=server)
    res = builder.refresh_index()
    assert res["status"] == "success"
    assert res["indexed_files"] == 1
    assert (server / "index.toml").exists()
    assert "old" not in (server / "pack.toml").read_text(encoding="utf-8")


def test_export_mrpack(tmp_path: Path):
    server = tmp_path / "server"
    server.mkdir()
    mods = server / "mods"
    mods.mkdir()
    config = server / "config"
    config.mkdir()
    (config / "subdir").mkdir()  # directory inside config to test is_file() == False
    datapacks = server / "datapacks"
    datapacks.mkdir()
    (datapacks / "subdir").mkdir()  # directory inside datapacks to test is_file() == False

    (mods / "test.pw.toml").write_text(
        'name = "test"\nfilename = "test-1.0.jar"\nside = "both"\nhash = "12345"\nurl = "https://cdn.example.com/test.jar"\n',
        encoding="utf-8",
    )
    # Add a .pw.toml with no filename to hit line 125
    (mods / "empty_filename.pw.toml").write_text(
        'name = "empty"\nside = "both"\nhash = "12345"\n',
        encoding="utf-8",
    )
    (config / "test.cfg").write_text("key=val\n", encoding="utf-8")
    (datapacks / "pack.zip").write_bytes(b"dummy zip")

    out_mrpack = tmp_path / "test.mrpack"
    builder = ModpackBuilder(server_dir=server)
    res_path = builder.export_mrpack(output_path=out_mrpack)

    assert res_path.exists()
    with zipfile.ZipFile(res_path, "r") as zf:
        namelist = zf.namelist()
        assert "modrinth.index.json" in namelist
        assert "overrides/config/test.cfg" in namelist
        assert "overrides/datapacks/pack.zip" in namelist

    # Test export when mods_dir, config_dir, datapacks_dir do not exist
    empty_server = tmp_path / "empty_srv"
    builder_empty = ModpackBuilder(server_dir=empty_server)
    out_empty = tmp_path / "empty.mrpack"
    res_empty = builder_empty.export_mrpack(output_path=out_empty)
    assert res_empty.exists()



def test_test_headless_server():
    builder = ModpackBuilder()

    # Case 1: Docker not found
    with patch("shutil.which", return_value=None):
        res = builder.test_headless_server()
        assert res["status"] == "skipped"

    # Case 2: Docker success
    with patch("shutil.which", return_value="/usr/bin/docker"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="Config valid")
            res = builder.test_headless_server()
            assert res["status"] == "success"

    # Case 3: Docker CalledProcessError
    with patch("shutil.which", return_value="/usr/bin/docker"):
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, ["docker"], stderr="syntax error")
            res = builder.test_headless_server()
            assert res["status"] == "error"
            assert "syntax error" in res["message"]

    # Case 4: Generic Exception
    with patch("shutil.which", return_value="/usr/bin/docker"):
        with patch("subprocess.run", side_effect=RuntimeError("timeout")):
            res = builder.test_headless_server()
            assert res["status"] == "error"


def test_main_cli(tmp_path: Path):
    with patch("mc_server_tools.modpack_builder.ModpackBuilder.validate_manifest", return_value={"valid": True}):
        with patch("sys.argv", ["modpack_builder", "--validate"]):
            assert main() == 0

    with patch("mc_server_tools.modpack_builder.ModpackBuilder.validate_manifest", return_value={"valid": False}):
        with patch("sys.argv", ["modpack_builder", "--validate"]):
            assert main() == 1

    with patch("mc_server_tools.modpack_builder.ModpackBuilder.refresh_index", return_value={"status": "success"}):
        with patch("sys.argv", ["modpack_builder", "--refresh"]):
            assert main() == 0

    with patch("mc_server_tools.modpack_builder.ModpackBuilder.export_mrpack", return_value=tmp_path / "out.mrpack"):
        with patch("sys.argv", ["modpack_builder", "--export", "out.mrpack"]):
            assert main() == 0

    with patch("mc_server_tools.modpack_builder.ModpackBuilder.test_headless_server", return_value={"status": "success"}):
        with patch("sys.argv", ["modpack_builder", "--test-server"]):
            assert main() == 0

    with patch("mc_server_tools.modpack_builder.ModpackBuilder.test_headless_server", return_value={"status": "error"}):
        with patch("sys.argv", ["modpack_builder", "--test-server"]):
            assert main() == 1

    with patch("mc_server_tools.modpack_builder.ModpackBuilder.validate_manifest", return_value={"valid": True}):
        with patch("sys.argv", ["modpack_builder"]):
            assert main() == 0
