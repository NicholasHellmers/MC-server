"""AWS Lightsail / EC2 provisioner module for Minecraft server deployment in São Paulo."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError


def load_env_file(env_path: Path | str = ".env") -> dict[str, str]:
    """Load key-value pairs from a .env file into os.environ if not already set."""
    path = Path(env_path)
    if not path.is_file():
        if str(env_path) == ".env":
            root_env = Path(__file__).resolve().parent.parent.parent / ".env"
            if root_env.is_file():
                path = root_env
            else:
                return {}
        else:
            return {}

    loaded: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        clean_line = line.strip()
        if not clean_line or clean_line.startswith("#") or "=" not in clean_line:
            continue
        key, val = clean_line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key:
            if key not in os.environ:
                os.environ[key] = val
            loaded[key] = val
    return loaded


def generate_cloud_init_script(
    repo_url: str = "https://github.com/NicholasHellmers/MC-server.git",
    rcon_password: str = "change_this_rcon_password",
    r2_account_id: str = "",
    r2_access_key_id: str = "",
    r2_secret_access_key: str = "",
    r2_bucket_name: str = "mc-cobblemon-backups",
    server_memory: str = "10G",
    server_motd: str = "§6Cobblemon Adventure §7| §aLatAm Server",
) -> str:
    """Generate a Cloud-Init startup script to bootstrap Docker and Minecraft on first boot."""
    return f"""#!/bin/bash
set -euo pipefail

# 1. Update and install Docker and Git
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y docker.io docker-compose-v2 git

systemctl enable --now docker
usermod -aG docker ubuntu || true

# 2. Clone repository into /opt/mc-server
mkdir -p /opt/mc-server
if [ ! -d "/opt/mc-server/.git" ]; then
    git clone "{repo_url}" /opt/mc-server
fi
chown -R ubuntu:ubuntu /opt/mc-server

# 3. Create production server/.env
cat << 'EOF' > /opt/mc-server/server/.env
SERVER_MEMORY={server_memory}
SERVER_MOTD={server_motd}
MAX_PLAYERS=16
VIEW_DISTANCE=10
SIMULATION_DISTANCE=8
DIFFICULTY=easy
ONLINE_MODE=true
PVP=true
ALLOW_FLIGHT=true

RCON_PASSWORD={rcon_password}

R2_BUCKET_NAME={r2_bucket_name}
R2_ACCOUNT_ID={r2_account_id}
R2_ACCESS_KEY_ID={r2_access_key_id}
R2_SECRET_ACCESS_KEY={r2_secret_access_key}
EOF

# 4. Start Minecraft server via Docker Compose
cd /opt/mc-server/server
docker compose up -d
"""


class AWSProvisioner:
    """Manages AWS Lightsail compute instances, static IPs, and firewall rules."""

    def __init__(
        self,
        region_name: str = "sa-east-1",
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        session: boto3.Session | None = None,
    ) -> None:
        load_env_file()
        self.region_name = region_name or os.getenv("AWS_REGION", "sa-east-1")
        access_key = aws_access_key_id or os.getenv("AWS_ACCESS_KEY_ID")
        secret_key = aws_secret_access_key or os.getenv("AWS_SECRET_ACCESS_KEY")

        if session:
            self.session = session
        elif access_key and secret_key:
            self.session = boto3.Session(
                region_name=self.region_name,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
            )
        else:
            self.session = boto3.Session(region_name=self.region_name)

        self._client: Any = None

    @property
    def client(self) -> Any:
        """Lazy initializer for the Lightsail client."""
        if self._client is None:
            self._client = self.session.client("lightsail", region_name=self.region_name)
        return self._client

    def resolve_bundle_id(self, requested_bundle: str = "medium") -> str:
        """Resolve bundle ID to an active valid bundle in the target region."""
        try:
            response = self.client.get_bundles(includeInactive=False)
            bundles = response.get("bundles", [])
        except Exception:
            bundles = []

        if not bundles:
            return requested_bundle

        # Check if exact match exists
        for b in bundles:
            if b.get("bundleId") == requested_bundle:
                return requested_bundle

        prefix = requested_bundle.split("_")[0].lower()
        ram_map = {
            "nano": 0.5,
            "micro": 1.0,
            "small": 2.0,
            "medium": 4.0,
            "large": 8.0,
            "xlarge": 16.0,
            "2xlarge": 32.0,
        }
        target_ram = ram_map.get(prefix, 4.0)

        # Try prefix match
        for b in bundles:
            b_id = b.get("bundleId", "")
            if b_id.startswith(f"{prefix}_"):
                return b_id

        # Fallback to closest RAM match
        closest = bundles[0].get("bundleId", requested_bundle)
        min_diff = 999.0
        for b in bundles:
            ram = b.get("ramSizeInGb", 0.0)
            diff = abs(ram - target_ram)
            if diff < min_diff:
                min_diff = diff
                closest = b.get("bundleId", closest)

        return closest

    def create_instance(
        self,
        instance_name: str,
        bundle_id: str = "medium",
        blueprint_id: str = "ubuntu_24_04",
        key_pair_name: str | None = None,
        user_data: str | None = None,
    ) -> dict[str, Any]:
        """Create a Lightsail instance for the Minecraft server."""
        resolved_bundle = self.resolve_bundle_id(bundle_id)
        kwargs: dict[str, Any] = {
            "instanceNames": [instance_name],
            "availabilityZone": f"{self.region_name}a",
            "blueprintId": blueprint_id,
            "bundleId": resolved_bundle,
        }
        if key_pair_name:
            kwargs["keyPairName"] = key_pair_name
        if user_data:
            kwargs["userData"] = user_data

        try:
            response = self.client.create_instances(**kwargs)
            return {"status": "success", "operations": response.get("operations", [])}
        except ClientError as e:
            return {"status": "error", "message": str(e)}

    def allocate_and_attach_static_ip(
        self,
        static_ip_name: str,
        instance_name: str,
    ) -> dict[str, Any]:
        """Allocate a static public IP and attach it to the server instance."""
        try:
            self.client.allocate_static_ip(staticIpName=static_ip_name)
            self.client.attach_static_ip(
                staticIpName=static_ip_name,
                instanceName=instance_name,
            )
            ip_info = self.client.get_static_ip(staticIpName=static_ip_name)
            ip_address = ip_info.get("staticIp", {}).get("ipAddress", "")
            if not ip_address:
                inst_res = self.get_instance_status(instance_name)
                ip_address = inst_res.get("public_ip") or "Allocated"
            return {"status": "success", "static_ip": ip_address}
        except ClientError as e:
            return {"status": "error", "message": str(e)}

    def configure_firewall_ports(
        self,
        instance_name: str,
        ports: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Open firewall ports for Minecraft (25565) and SSH (22)."""
        target_ports = ports or [
            {"fromPort": 22, "toPort": 22, "protocol": "tcp"},
            {"fromPort": 25565, "toPort": 25565, "protocol": "tcp"},
            {"fromPort": 25565, "toPort": 25565, "protocol": "udp"},
        ]
        results: list[dict[str, Any]] = []
        for port_info in target_ports:
            try:
                self.client.open_instance_public_ports(
                    instanceName=instance_name,
                    portInfo=port_info,
                )
                results.append({"port": port_info["fromPort"], "status": "opened"})
            except ClientError as e:
                results.append({"port": port_info["fromPort"], "status": "error", "message": str(e)})

        return {"status": "completed", "details": results}

    def get_instance_status(self, instance_name: str) -> dict[str, Any]:
        """Check status and IP address of a Lightsail instance."""
        try:
            response = self.client.get_instance(instanceName=instance_name)
            instance = response.get("instance", {})
            return {
                "status": "success",
                "name": instance.get("name"),
                "state": instance.get("state", {}).get("name"),
                "public_ip": instance.get("publicIpAddress"),
            }
        except ClientError as e:
            return {"status": "error", "message": str(e)}

    def provision_all_in_one(
        self,
        instance_name: str = "mc-cobblemon-server",
        bundle_id: str = "medium",
        key_pair_name: str | None = None,
        rcon_password: str | None = None,
        r2_account_id: str | None = None,
        r2_access_key_id: str | None = None,
        r2_secret_access_key: str | None = None,
        r2_bucket_name: str | None = None,
    ) -> dict[str, Any]:
        """Perform zero-touch 1-click cloud deployment."""
        cloud_init = generate_cloud_init_script(
            rcon_password=rcon_password or os.getenv("RCON_PASSWORD", "secure_rcon_pass"),
            r2_account_id=r2_account_id or os.getenv("R2_ACCOUNT_ID", ""),
            r2_access_key_id=r2_access_key_id or os.getenv("R2_ACCESS_KEY_ID", ""),
            r2_secret_access_key=r2_secret_access_key or os.getenv("R2_SECRET_ACCESS_KEY", ""),
            r2_bucket_name=r2_bucket_name or os.getenv("R2_BUCKET_NAME", "mc-cobblemon-backups"),
        )

        # 1. Create VM
        create_res = self.create_instance(
            instance_name=instance_name,
            bundle_id=bundle_id,
            key_pair_name=key_pair_name,
            user_data=cloud_init,
        )
        if create_res.get("status") != "success":
            return create_res

        # 2. Attach Static IP
        ip_name = f"{instance_name}-ip"
        ip_res = self.allocate_and_attach_static_ip(static_ip_name=ip_name, instance_name=instance_name)

        # 3. Open Ports
        fw_res = self.configure_firewall_ports(instance_name=instance_name)

        static_ip = ip_res.get("static_ip", "Pending")
        return {
            "status": "success",
            "instance_name": instance_name,
            "static_ip": static_ip,
            "firewall": fw_res,
            "server_address": f"{static_ip}:25565",
            "message": f"Server provisioned! Connect via Minecraft at {static_ip}:25565 in ~2-3 minutes.",
        }


def main() -> int:
    """CLI entrypoint for AWS Lightsail provisioning."""
    parser = argparse.ArgumentParser(description="Provision AWS Lightsail Minecraft host.")
    parser.add_argument("--name", default="mc-cobblemon-server", help="Instance name")
    parser.add_argument("--region", default="sa-east-1", help="AWS region (default: sa-east-1)")
    parser.add_argument("--plan", default="medium", help="Lightsail bundle plan (e.g. medium, large)")
    parser.add_argument("--key", default=None, help="Lightsail key pair name")
    parser.add_argument("--status", action="store_true", help="Check status and IP of existing instance")
    args = parser.parse_args()

    load_env_file()
    if not os.getenv("AWS_ACCESS_KEY_ID") or not os.getenv("AWS_SECRET_ACCESS_KEY"):
        print(
            "ERROR: Missing AWS credentials!\n"
            "Please create a .env file in the repository root with:\n"
            "  AWS_ACCESS_KEY_ID=your_key\n"
            "  AWS_SECRET_ACCESS_KEY=your_secret\n",
            file=sys.stderr,
        )
        return 1

    provisioner = AWSProvisioner(region_name=args.region)

    if args.status:
        status_res = provisioner.get_instance_status(args.name)
        ip = status_res.get("public_ip", "Unknown")
        state = status_res.get("state", "Unknown")
        print(f"Instance '{args.name}' Status: {state} | Static Public IP: {ip} | Server: {ip}:25565")
        return 0 if status_res.get("status") == "success" else 1

    print(f"Launching zero-touch Minecraft server '{args.name}' in {args.region}...")
    res = provisioner.provision_all_in_one(
        instance_name=args.name,
        bundle_id=args.plan,
        key_pair_name=args.key,
    )
    print(f"Result: {res}")
    return 0 if res.get("status") == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
