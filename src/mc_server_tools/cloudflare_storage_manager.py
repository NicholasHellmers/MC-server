"""Cloudflare R2 Object Storage manager using S3-compatible API for offsite backups."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError


from mc_server_tools.aws_provisioner import load_env_file


class CloudflareStorageManager:
    """Manages Cloudflare R2 backup buckets via S3 API."""

    def __init__(
        self,
        account_id: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        session: boto3.Session | None = None,
    ) -> None:
        load_env_file()
        self.account_id = account_id or os.getenv("R2_ACCOUNT_ID", "")
        self.access_key_id = access_key_id or os.getenv("R2_ACCESS_KEY_ID", "")
        self.secret_access_key = secret_access_key or os.getenv("R2_SECRET_ACCESS_KEY", "")
        self.endpoint_url = (
            f"https://{self.account_id}.r2.cloudflarestorage.com" if self.account_id else ""
        )
        self.session = session or boto3.Session()
        self._s3_client: Any = None

    @property
    def s3_client(self) -> Any:
        """Lazy initializer for S3 client configured for Cloudflare R2."""
        if self._s3_client is None:
            self._s3_client = self.session.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                region_name="auto",
            )
        return self._s3_client

    def create_bucket(self, bucket_name: str) -> dict[str, Any]:
        """Create a new bucket in Cloudflare R2."""
        try:
            self.s3_client.create_bucket(Bucket=bucket_name)
            return {"status": "success", "bucket": bucket_name}
        except ClientError as e:
            return {"status": "error", "message": str(e)}

    def list_buckets(self) -> dict[str, Any]:
        """List all buckets in the Cloudflare R2 account."""
        try:
            response = self.s3_client.list_buckets()
            buckets = [b.get("Name", "") for b in response.get("Buckets", [])]
            return {"status": "success", "buckets": buckets}
        except ClientError as e:
            return {"status": "error", "message": str(e)}

    def upload_file(
        self,
        bucket_name: str,
        key: str,
        file_path: Path | str,
    ) -> dict[str, Any]:
        """Upload a file or backup archive to Cloudflare R2."""
        path = Path(file_path)
        if not path.is_file():
            return {"status": "error", "message": f"Local file not found: {path}"}
        try:
            self.s3_client.upload_file(str(path), bucket_name, key)
            return {"status": "success", "key": key, "bucket": bucket_name}
        except ClientError as e:
            return {"status": "error", "message": str(e)}

    def list_backups(
        self,
        bucket_name: str,
        prefix: str = "backups/",
    ) -> dict[str, Any]:
        """List backup archives stored under a prefix."""
        try:
            response = self.s3_client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
            contents = response.get("Contents", [])
            backups = [
                {
                    "key": item.get("Key"),
                    "size_bytes": item.get("Size"),
                    "last_modified": str(item.get("LastModified")),
                }
                for item in contents
            ]
            return {"status": "success", "backups": backups}
        except ClientError as e:
            return {"status": "error", "message": str(e)}

    def verify_connectivity(self, bucket_name: str) -> dict[str, Any]:
        """Verify read/write capability to the R2 bucket."""
        test_key = ".healthcheck"
        try:
            self.s3_client.put_object(Bucket=bucket_name, Key=test_key, Body=b"ok")
            self.s3_client.delete_object(Bucket=bucket_name, Key=test_key)
            return {
                "status": "success",
                "message": f"Connected successfully to Cloudflare R2 bucket '{bucket_name}'.",
            }
        except ClientError as e:
            return {"status": "error", "message": str(e)}


def main() -> int:
    """CLI entrypoint for Cloudflare R2 storage manager."""
    parser = argparse.ArgumentParser(description="Manage Cloudflare R2 backup storage.")
    parser.add_argument("--bucket-name", default="mc-cobblemon-backups", help="R2 bucket name")
    parser.add_argument("--verify", action="store_true", help="Verify R2 connectivity")
    parser.add_argument("--create", action="store_true", help="Create bucket")
    args = parser.parse_args()

    manager = CloudflareStorageManager()
    if args.create:
        res = manager.create_bucket(args.bucket_name)
        print(f"Create bucket result: {res}")
        return 0 if res.get("status") == "success" else 1

    res = manager.verify_connectivity(args.bucket_name)
    print(f"Connectivity result: {res}")
    return 0 if res.get("status") == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
