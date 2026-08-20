"""Tests for aws_provisioner module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError
from mc_server_tools.aws_provisioner import (
    AWSProvisioner,
    generate_cloud_init_script,
    load_env_file,
    main,
)


def test_load_env_file(tmp_path: Path):
    # Nonexistent custom path
    assert load_env_file(tmp_path / "nonexistent.env") == {}

    # Valid env file with new key, already existing key, and empty key
    import os
    os.environ["ALREADY_SET_TEST_KEY"] = "original"
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# Comment line\n\nTEST_KEY_ONE=value1\nTEST_KEY_TWO='value2'\nALREADY_SET_TEST_KEY=new_val\n=empty_key\nINVALID_LINE\n",
        encoding="utf-8",
    )
    loaded = load_env_file(env_file)
    assert loaded.get("TEST_KEY_ONE") == "value1"
    assert loaded.get("TEST_KEY_TWO") == "value2"
    assert loaded.get("ALREADY_SET_TEST_KEY") == "new_val"
    assert os.environ["ALREADY_SET_TEST_KEY"] == "original"

    # Default .env when root .env exists
    with patch("pathlib.Path.is_file") as mock_is_file:
        mock_is_file.side_effect = [False, True]
        with patch("pathlib.Path.read_text", return_value="FALLBACK_KEY=val\n"):
            res = load_env_file(".env")
            assert "FALLBACK_KEY" in res

    # Default .env when root .env does not exist
    with patch("pathlib.Path.is_file") as mock_is_file:
        mock_is_file.side_effect = [False, False]
        res = load_env_file(".env")
        assert res == {}


def test_generate_cloud_init_script():
    script = generate_cloud_init_script(
        repo_url="https://github.com/test/repo.git",
        rcon_password="secret_rcon_pass",
        r2_account_id="acc123",
        r2_access_key_id="key123",
        r2_secret_access_key="sec123",
    )
    assert "#!/bin/bash" in script
    assert "docker.io" in script
    assert "secret_rcon_pass" in script
    assert "acc123" in script


def test_aws_provisioner_client_init_variations():
    # Explicit keys
    p_keys = AWSProvisioner(
        region_name="sa-east-1",
        aws_access_key_id="AKIA123",
        aws_secret_access_key="SEC123",
    )
    assert p_keys.session is not None

    # Custom session
    session_mock = MagicMock()
    provisioner = AWSProvisioner(region_name="sa-east-1", session=session_mock)
    _ = provisioner.client
    session_mock.client.assert_called_once_with("lightsail", region_name="sa-east-1")

    # Fallback default session (no keys, no session)
    with patch.dict("os.environ", {}, clear=True):
        with patch("mc_server_tools.aws_provisioner.load_env_file", return_value={}):
            p_fallback = AWSProvisioner(region_name="sa-east-1")
            assert p_fallback.session is not None


def test_resolve_bundle_id():
    client_mock = MagicMock()
    provisioner = AWSProvisioner(region_name="sa-east-1")
    provisioner._client = client_mock

    # Exception from client -> returns requested
    client_mock.get_bundles.side_effect = RuntimeError("API error")
    assert provisioner.resolve_bundle_id("medium_3_0") == "medium_3_0"

    # Empty list -> returns requested
    client_mock.get_bundles.side_effect = None
    client_mock.get_bundles.return_value = {"bundles": []}
    assert provisioner.resolve_bundle_id("medium_3_0") == "medium_3_0"

    # Exact match
    client_mock.get_bundles.return_value = {
        "bundles": [
            {"bundleId": "nano_2_0", "ramSizeInGb": 0.5},
            {"bundleId": "medium_2_0", "ramSizeInGb": 4.0},
            {"bundleId": "large_2_0", "ramSizeInGb": 8.0},
        ]
    }
    assert provisioner.resolve_bundle_id("medium_2_0") == "medium_2_0"

    # Prefix match (medium_3_0 -> medium_2_0)
    assert provisioner.resolve_bundle_id("medium_3_0") == "medium_2_0"
    assert provisioner.resolve_bundle_id("large_3_0") == "large_2_0"

    # Default fallback when prefix not found in map
    assert provisioner.resolve_bundle_id("custom_bundle") == "medium_2_0"


def test_create_instance_success():
    client_mock = MagicMock()
    client_mock.create_instances.return_value = {"operations": [{"id": "op-1"}]}
    provisioner = AWSProvisioner(region_name="sa-east-1")
    provisioner._client = client_mock

    res = provisioner.create_instance(
        instance_name="mc-server",
        key_pair_name="my-key",
        user_data="#!/bin/bash",
    )
    assert res["status"] == "success"
    assert len(res["operations"]) == 1


def test_create_instance_client_error():
    client_mock = MagicMock()
    client_mock.create_instances.side_effect = ClientError(
        {"Error": {"Code": "InvalidParam", "Message": "Bad request"}},
        "CreateInstances",
    )
    provisioner = AWSProvisioner(region_name="sa-east-1")
    provisioner._client = client_mock

    res = provisioner.create_instance(instance_name="mc-server")
    assert res["status"] == "error"
    assert "Bad request" in res["message"]


def test_allocate_and_attach_static_ip_success():
    client_mock = MagicMock()
    client_mock.get_static_ip.return_value = {
        "staticIp": {"ipAddress": "18.230.10.20", "name": "mc-ip"}
    }
    provisioner = AWSProvisioner(region_name="sa-east-1")
    provisioner._client = client_mock

    res = provisioner.allocate_and_attach_static_ip("mc-ip", "mc-server")
    assert res["status"] == "success"
    assert res["static_ip"] == "18.230.10.20"


def test_allocate_and_attach_static_ip_error():
    client_mock = MagicMock()
    client_mock.allocate_static_ip.side_effect = ClientError(
        {"Error": {"Code": "LimitExceeded", "Message": "Limit reached"}},
        "AllocateStaticIp",
    )
    provisioner = AWSProvisioner(region_name="sa-east-1")
    provisioner._client = client_mock

    res = provisioner.allocate_and_attach_static_ip("mc-ip", "mc-server")
    assert res["status"] == "error"
    assert "Limit reached" in res["message"]


def test_configure_firewall_ports_success():
    client_mock = MagicMock()
    provisioner = AWSProvisioner(region_name="sa-east-1")
    provisioner._client = client_mock

    res = provisioner.configure_firewall_ports("mc-server")
    assert res["status"] == "completed"
    assert len(res["details"]) == 3
    assert all(d["status"] == "opened" for d in res["details"])


def test_configure_firewall_ports_error():
    client_mock = MagicMock()
    client_mock.open_instance_public_ports.side_effect = ClientError(
        {"Error": {"Code": "PortError", "Message": "Port failed"}},
        "OpenInstancePublicPorts",
    )
    provisioner = AWSProvisioner(region_name="sa-east-1")
    provisioner._client = client_mock

    res = provisioner.configure_firewall_ports(
        "mc-server",
        ports=[{"fromPort": 25565, "toPort": 25565, "protocol": "tcp"}],
    )
    assert res["status"] == "completed"
    assert res["details"][0]["status"] == "error"


def test_get_instance_status_success():
    client_mock = MagicMock()
    client_mock.get_instance.return_value = {
        "instance": {
            "name": "mc-server",
            "state": {"name": "running"},
            "publicIpAddress": "54.232.1.2",
        }
    }
    provisioner = AWSProvisioner(region_name="sa-east-1")
    provisioner._client = client_mock

    res = provisioner.get_instance_status("mc-server")
    assert res["status"] == "success"
    assert res["public_ip"] == "54.232.1.2"
    assert res["state"] == "running"


def test_get_instance_status_error():
    client_mock = MagicMock()
    client_mock.get_instance.side_effect = ClientError(
        {"Error": {"Code": "NotFound", "Message": "Instance not found"}},
        "GetInstance",
    )
    provisioner = AWSProvisioner(region_name="sa-east-1")
    provisioner._client = client_mock

    res = provisioner.get_instance_status("mc-server")
    assert res["status"] == "error"


def test_provision_all_in_one_success_and_failure():
    provisioner = AWSProvisioner(region_name="sa-east-1")

    # Failure at create_instance
    with patch.object(provisioner, "create_instance", return_value={"status": "error", "message": "Failed"}):
        res_fail = provisioner.provision_all_in_one(instance_name="mc-server")
        assert res_fail["status"] == "error"

    # Full success
    with patch.object(provisioner, "create_instance", return_value={"status": "success"}), \
         patch.object(provisioner, "allocate_and_attach_static_ip", return_value={"status": "success", "static_ip": "18.230.1.2"}), \
         patch.object(provisioner, "configure_firewall_ports", return_value={"status": "completed"}):
        res_ok = provisioner.provision_all_in_one(
            instance_name="mc-server",
            rcon_password="pass",
            r2_account_id="acc",
            r2_access_key_id="key",
            r2_secret_access_key="sec",
        )
        assert res_ok["status"] == "success"
        assert res_ok["static_ip"] == "18.230.1.2"
        assert "18.230.1.2:25565" in res_ok["server_address"]


def test_allocate_and_attach_static_ip_empty_fallback():
    client_mock = MagicMock()
    client_mock.get_static_ip.return_value = {"staticIp": {}}
    client_mock.get_instance.return_value = {
        "instance": {"publicIpAddress": "18.230.99.99"}
    }
    provisioner = AWSProvisioner(region_name="sa-east-1")
    provisioner._client = client_mock

    res = provisioner.allocate_and_attach_static_ip("mc-ip", "mc-server")
    assert res["status"] == "success"
    assert res["static_ip"] == "18.230.99.99"


def test_main_cli_missing_credentials():
    with patch.dict("os.environ", {}, clear=True):
        with patch("mc_server_tools.aws_provisioner.load_env_file", return_value={}):
            with patch("sys.argv", ["aws_provisioner", "--name", "test-srv"]):
                assert main() == 1


def test_main_cli_status_success_and_failure():
    with patch.dict("os.environ", {"AWS_ACCESS_KEY_ID": "AKIA1", "AWS_SECRET_ACCESS_KEY": "SEC1"}):
        with patch("mc_server_tools.aws_provisioner.AWSProvisioner.get_instance_status") as mock_st:
            mock_st.return_value = {"status": "success", "public_ip": "18.230.1.2", "state": "running"}
            with patch("sys.argv", ["aws_provisioner", "--name", "test-srv", "--status"]):
                assert main() == 0

        with patch("mc_server_tools.aws_provisioner.AWSProvisioner.get_instance_status") as mock_st:
            mock_st.return_value = {"status": "error"}
            with patch("sys.argv", ["aws_provisioner", "--name", "test-srv", "--status"]):
                assert main() == 1


def test_main_cli_success():
    with patch.dict("os.environ", {"AWS_ACCESS_KEY_ID": "AKIA1", "AWS_SECRET_ACCESS_KEY": "SEC1"}):
        with patch("mc_server_tools.aws_provisioner.AWSProvisioner.provision_all_in_one") as mock_all:
            mock_all.return_value = {"status": "success"}
            with patch("sys.argv", ["aws_provisioner", "--name", "test-srv"]):
                assert main() == 0


def test_main_cli_failure():
    with patch.dict("os.environ", {"AWS_ACCESS_KEY_ID": "AKIA1", "AWS_SECRET_ACCESS_KEY": "SEC1"}):
        with patch("mc_server_tools.aws_provisioner.AWSProvisioner.provision_all_in_one") as mock_all:
            mock_all.return_value = {"status": "error"}
            with patch("sys.argv", ["aws_provisioner", "--name", "test-srv"]):
                assert main() == 1
