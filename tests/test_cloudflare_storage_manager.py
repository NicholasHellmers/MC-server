"""Tests for cloudflare_storage_manager module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError
from mc_server_tools.cloudflare_storage_manager import CloudflareStorageManager, main


def test_cloudflare_storage_manager_init():
    mgr = CloudflareStorageManager(
        account_id="acc123",
        access_key_id="key123",
        secret_access_key="sec123",
    )
    assert mgr.endpoint_url == "https://acc123.r2.cloudflarestorage.com"
    _ = mgr.s3_client
    assert mgr._s3_client is not None


def test_create_bucket_success_and_error():
    client_mock = MagicMock()
    mgr = CloudflareStorageManager(account_id="acc123")
    mgr._s3_client = client_mock

    # Success
    res = mgr.create_bucket("my-bucket")
    assert res["status"] == "success"

    # Error
    client_mock.create_bucket.side_effect = ClientError(
        {"Error": {"Code": "BucketAlreadyExists", "Message": "Exists"}},
        "CreateBucket",
    )
    res_err = mgr.create_bucket("my-bucket")
    assert res_err["status"] == "error"


def test_list_buckets_success_and_error():
    client_mock = MagicMock()
    client_mock.list_buckets.return_value = {"Buckets": [{"Name": "b1"}, {"Name": "b2"}]}
    mgr = CloudflareStorageManager(account_id="acc123")
    mgr._s3_client = client_mock

    res = mgr.list_buckets()
    assert res["status"] == "success"
    assert res["buckets"] == ["b1", "b2"]

    client_mock.list_buckets.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "Denied"}},
        "ListBuckets",
    )
    res_err = mgr.list_buckets()
    assert res_err["status"] == "error"


def test_upload_file(tmp_path: Path):
    client_mock = MagicMock()
    mgr = CloudflareStorageManager(account_id="acc123")
    mgr._s3_client = client_mock

    # File not found
    res_nf = mgr.upload_file("b1", "k1", tmp_path / "nonexistent.tar.gz")
    assert res_nf["status"] == "error"
    assert "not found" in res_nf["message"]

    # Success
    real_file = tmp_path / "backup.tar.gz"
    real_file.write_bytes(b"backup bytes")
    res = mgr.upload_file("b1", "k1", real_file)
    assert res["status"] == "success"

    # S3 Error
    client_mock.upload_file.side_effect = ClientError(
        {"Error": {"Code": "UploadFailed", "Message": "Failed"}},
        "UploadFile",
    )
    res_err = mgr.upload_file("b1", "k1", real_file)
    assert res_err["status"] == "error"


def test_list_backups_success_and_error():
    client_mock = MagicMock()
    client_mock.list_objects_v2.return_value = {
        "Contents": [
            {"Key": "backups/world-2026.tar.gz", "Size": 1024, "LastModified": "2026-08-19"}
        ]
    }
    mgr = CloudflareStorageManager(account_id="acc123")
    mgr._s3_client = client_mock

    res = mgr.list_backups("my-bucket")
    assert res["status"] == "success"
    assert len(res["backups"]) == 1
    assert res["backups"][0]["key"] == "backups/world-2026.tar.gz"

    client_mock.list_objects_v2.side_effect = ClientError(
        {"Error": {"Code": "NoSuchBucket", "Message": "No bucket"}},
        "ListObjectsV2",
    )
    res_err = mgr.list_backups("my-bucket")
    assert res_err["status"] == "error"


def test_verify_connectivity_success_and_error():
    client_mock = MagicMock()
    mgr = CloudflareStorageManager(account_id="acc123")
    mgr._s3_client = client_mock

    # Success
    res = mgr.verify_connectivity("my-bucket")
    assert res["status"] == "success"

    # Error
    client_mock.put_object.side_effect = ClientError(
        {"Error": {"Code": "InvalidAccessKeyId", "Message": "Invalid key"}},
        "PutObject",
    )
    res_err = mgr.verify_connectivity("my-bucket")
    assert res_err["status"] == "error"


def test_main_cli():
    with patch("mc_server_tools.cloudflare_storage_manager.CloudflareStorageManager.verify_connectivity") as mock_v:
        mock_v.return_value = {"status": "success"}
        with patch("sys.argv", ["cloudflare_storage_manager", "--bucket-name", "test-b"]):
            assert main() == 0

    with patch("mc_server_tools.cloudflare_storage_manager.CloudflareStorageManager.verify_connectivity") as mock_v:
        mock_v.return_value = {"status": "error"}
        with patch("sys.argv", ["cloudflare_storage_manager", "--bucket-name", "test-b"]):
            assert main() == 1

    with patch("mc_server_tools.cloudflare_storage_manager.CloudflareStorageManager.create_bucket") as mock_c:
        mock_c.return_value = {"status": "success"}
        with patch("sys.argv", ["cloudflare_storage_manager", "--create", "--bucket-name", "test-b"]):
            assert main() == 0

    with patch("mc_server_tools.cloudflare_storage_manager.CloudflareStorageManager.create_bucket") as mock_c:
        mock_c.return_value = {"status": "error"}
        with patch("sys.argv", ["cloudflare_storage_manager", "--create", "--bucket-name", "test-b"]):
            assert main() == 1
