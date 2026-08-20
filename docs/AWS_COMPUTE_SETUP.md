# AWS Compute Setup Guide (Zero-Touch 1-Click Launch)

This guide walks you through launching your **Fabric 1.21.1 Cobblemon** cloud server in **São Paulo (`sa-east-1`)** with **zero manual terminal setup or SSH juggling**.

---

## What You Need from AWS (One-Time Setup)

You only need to interact with the AWS Console **once** to generate your API keys:

1. Log into your [AWS Management Console](https://aws.amazon.com/console/).
2. In the top search bar, type **IAM** &rarr; Select **Users** &rarr; Click **Create user**.
3. User name: `mc-admin`.
4. Permissions: Select **Attach policies directly** &rarr; Search and select `AmazonLightsailFullAccess` (or AdministratorAccess).
5. Complete user creation &rarr; Click the `mc-admin` user &rarr; Go to the **Security credentials** tab.
6. Under **Access keys**, click **Create access key** &rarr; Select **Command Line Interface (CLI)** &rarr; Check the box &rarr; Click **Create access key**.
7. Copy:
   * `AWS_ACCESS_KEY_ID`
   * `AWS_SECRET_ACCESS_KEY`

---

## 1-Click Automated Launch

### Step 1: Add Credentials to `.env`
In your local repository root, copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Fill in your secrets:
```ini
AWS_REGION=sa-east-1
AWS_ACCESS_KEY_ID=your_aws_access_key_id
AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key

# Any secure password for internal backup coordination
RCON_PASSWORD=my_secure_rcon_pass_2026

# Cloudflare R2 backup secrets
R2_BUCKET_NAME=mc-cobblemon-backups
R2_ACCOUNT_ID=your_cloudflare_account_id
R2_ACCESS_KEY_ID=your_r2_access_key_id
R2_SECRET_ACCESS_KEY=your_r2_secret_access_key
```

---

### Step 2: Run the 1-Click Launch Command

Execute the provisioner via UV:

```bash
python -m uv run python -m mc_server_tools.aws_provisioner --name mc-cobblemon-server --region sa-east-1
```

### What the Script Does Automatically (Zero Manual Work):
1. ✅ Provisions an Ubuntu 24.04 VM in São Paulo (`sa-east-1`).
2. ✅ Allocates and attaches a permanent Static Public IP.
3. ✅ Opens firewall ports for **Minecraft (25565/tcp & 25565/udp)** and **SSH (22/tcp)**.
4. ✅ Injects a Cloud-Init startup script that automatically:
   * Installs Docker & Docker Compose.
   * Clones this Git repository to `/opt/mc-server`.
   * Injects your `RCON_PASSWORD` and Cloudflare R2 backup credentials into `server/.env`.
   * Starts the Minecraft server and backup containers (`docker compose up -d`).

---

## Step 3: Connect & Play!

In **~2–3 minutes** after running the script, your server is completely bootstrapped and online.

* **Server Address to join in Minecraft / Modrinth App:** `<YOUR_STATIC_IP>:25565`
* (Optional) Point your domain name (e.g. `play.cobblemon.xyz`) to this Static IP via an A record in Cloudflare.
