# Cloudflare R2 Backup Storage Setup Guide (Zero-to-Hero)

This guide walks you through setting up **Cloudflare R2 Object Storage** for automated offsite disaster recovery backups with **$0 egress fees**.

---

## Step 1: Create an R2 Bucket in Cloudflare Dashboard

1. Log into your [Cloudflare Dashboard](https://dash.cloudflare.com/).
2. In the left sidebar, click **R2 Object Storage** (under Storage & Databases).
3. If this is your first time using R2, click **Enable R2**.
4. Click **Create bucket**.
5. Set Bucket Name: `mc-cobblemon-backups`.
6. Leave Location as **Automatic** (or select South America if available).
7. Click **Create bucket**.

---

## Step 2: Generate S3-Compatible API Credentials

1. On the main **R2 Object Storage** overview page, look at the right sidebar and click **Manage R2 API Tokens**.
2. Click **Create API Token**.
3. Name your token: `minecraft-backup-token`.
4. Permissions: Select **Object Read & Write**.
5. Specify bucket: Select `mc-cobblemon-backups` (or Apply to all buckets).
6. TTL: Set to **Forever** (or maximum duration).
7. Click **Create API Token**.
8. Cloudflare will display your credentials:
   * **Account ID** (found in your URL or dashboard sidebar)
   * **Access Key ID**
   * **Secret Access Key**
   * **Jurisdiction-specific S3 Endpoint URL** (e.g. `https://<account_id>.r2.cloudflarestorage.com`)

---

## Step 3: Configure Credentials in `.env`

Add your R2 credentials to your local `.env` and your cloud server's `server/.env`:

```ini
R2_BUCKET_NAME=mc-cobblemon-backups
R2_ACCOUNT_ID=your_cloudflare_account_id_here
R2_ACCESS_KEY_ID=your_r2_access_key_id_here
R2_SECRET_ACCESS_KEY=your_r2_secret_access_key_here
```

---

## Step 4: Verify Connectivity via UV

Verify that your Python tool can connect to Cloudflare R2 and write to the bucket:

```bash
uv run python -m mc_server_tools.cloudflare_storage_manager --verify --bucket-name mc-cobblemon-backups
```

Expected output:
```
Connected successfully to Cloudflare R2 bucket 'mc-cobblemon-backups'.
```

---

## Step 5: How Backups Run in Production

The `itzg/mc-backup` service in `server/docker-compose.yml` automatically:
1. Connects to the running Minecraft server via RCON every 6 hours.
2. Runs `/save-off` and `/save-all flush` to ensure all player data and world chunks are safely flushed to disk.
3. Compresses the `./data/world` directory into an encrypted `.tar.gz` archive.
4. Uploads the snapshot directly to your Cloudflare R2 bucket (`s3://mc-cobblemon-backups/backups/`).
5. Runs `/save-on` to resume normal disk saving.
6. Automatically prunes backups older than 14 days.
