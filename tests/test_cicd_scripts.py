"""Tests for cicd automation scripts."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from cicd.build_modpack import main as build_main, run_build
from cicd.deploy_server import execute_remote_deploy, main as deploy_main
from cicd.discord_notify import main as discord_main, send_discord_notification


def test_cicd_build_modpack(tmp_path: Path):
    # Validation failure case
    with patch("mc_server_tools.modpack_builder.ModpackBuilder.validate_manifest", return_value={"valid": False, "errors": ["err"]}):
        assert run_build(server_dir=tmp_path) == 1

    # Validation success case
    with patch("mc_server_tools.modpack_builder.ModpackBuilder.validate_manifest", return_value={
        "valid": True, "total_mods": 10, "client_only_mods": 2, "server_only_mods": 2, "shared_mods": 6
    }):
        with patch("mc_server_tools.modpack_builder.ModpackBuilder.export_mrpack") as mock_exp:
            dummy_out = tmp_path / "out.mrpack"
            dummy_out.write_bytes(b"dummy")
            mock_exp.return_value = dummy_out
            assert run_build(server_dir=tmp_path) == 0

    with patch("cicd.build_modpack.run_build", return_value=0):
        with patch("sys.argv", ["build_modpack"]):
            assert build_main() == 0


def test_cicd_discord_notify():
    # Missing webhook
    res_no_hook = send_discord_notification(webhook_url="", version_tag="v1.0", release_url="https://rel")
    assert res_no_hook["status"] == "error"

    # Success 200
    with patch("requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=204)
        res_ok = send_discord_notification(webhook_url="https://discord.com/api/webhooks/1/2", version_tag="v1.0", release_url="https://rel")
        assert res_ok["status"] == "success"

    # HTTP Error 400
    with patch("requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=400, text="Bad Request")
        res_err = send_discord_notification(webhook_url="https://discord.com/api/webhooks/1/2", version_tag="v1.0", release_url="https://rel")
        assert res_err["status"] == "error"

    # Exception
    with patch("requests.post", side_effect=RuntimeError("connection error")):
        res_exc = send_discord_notification(webhook_url="https://discord.com/api/webhooks/1/2", version_tag="v1.0", release_url="https://rel")
        assert res_exc["status"] == "error"

    # Main CLI
    with patch("cicd.discord_notify.send_discord_notification", return_value={"status": "success"}):
        with patch("sys.argv", ["discord_notify"]):
            assert discord_main() == 0

    with patch("cicd.discord_notify.send_discord_notification", return_value={"status": "error"}):
        with patch("sys.argv", ["discord_notify"]):
            assert discord_main() == 1


def test_cicd_deploy_server(tmp_path: Path):
    # Missing host
    res_no_host = execute_remote_deploy(host="")
    assert res_no_host["status"] == "error"

    key_file = tmp_path / "id_rsa"
    key_file.write_text("dummy key")

    # Success with key path
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="updated", stderr="")
        res = execute_remote_deploy(host="1.2.3.4", ssh_key_path=str(key_file))
        assert res["status"] == "success"

    # CalledProcessError
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(1, ["ssh"], output="fail", stderr="err")
        res_err = execute_remote_deploy(host="1.2.3.4")
        assert res_err["status"] == "error"

    # Generic Exception
    with patch("subprocess.run", side_effect=RuntimeError("ssh timeout")):
        res_exc = execute_remote_deploy(host="1.2.3.4")
        assert res_exc["status"] == "error"

    # Main CLI
    with patch("cicd.deploy_server.execute_remote_deploy", return_value={"status": "success"}):
        with patch("sys.argv", ["deploy_server"]):
            assert deploy_main() == 0

    with patch("cicd.deploy_server.execute_remote_deploy", return_value={"status": "error"}):
        with patch("sys.argv", ["deploy_server"]):
            assert deploy_main() == 1
