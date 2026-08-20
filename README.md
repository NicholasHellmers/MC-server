# Cobblemon Fabric 1.21.1 Cloud Server & Modpack SSOT

This repository contains the complete **Single Source of Truth (SSOT)** modpack definition, cloud deployment orchestration, and GitOps automation for the **Cobblemon Adventure** Minecraft server.

---

## Architecture Overview

* **Compute Layer**: **AWS Lightsail / EC2** in São Paulo (`sa-east-1`) providing 99.99% SLA uptime, fast NVMe I/O, and ~25–35ms latency to Paraguay / LatAm South.
* **Storage & Disaster Recovery Layer**: **Cloudflare R2 Object Storage** via S3-compatible API for automated, atomic RCON snapshots with **$0 egress fees**.
* **Modpack SSOT**: Declarative Git repository using **`packwiz`** (.pw.toml metadata) strictly separating `client`, `server`, and `both` mod environments.
* **Client Distribution**: Automated **GitHub Releases** exporting `.mrpack` packages + instant **Discord Webhook** announcements.
* **100% Code Coverage Policy**: Strict `--cov-fail-under=100` enforcement on all Python tools in `src/` and `cicd/`, supported by a custom Antigravity workspace skill (`.agents/skills/code-coverage-report/`).

---

## Directory Layout

```
MC-server/
├── .agents/skills/code-coverage-report/ # Custom workspace skill enforcing 100% test coverage
├── .github/workflows/                 # CI/CD workflows for testing and release deployments
├── cicd/                              # Reusable CI/CD automation scripts
├── docs/                              # Zero-to-hero onboarding and administration guides
│   ├── AWS_COMPUTE_SETUP.md           # AWS account, IAM, and instance provisioning guide
│   ├── CLOUDFLARE_STORAGE_SETUP.md    # Cloudflare R2 bucket & API token guide
│   ├── MODPACK_ADMIN_GUIDE.md         # Modpack development & release manual
│   └── PLAYER_INSTALLATION_GUIDE.md   # 3-step community player guide for Modrinth App
├── pyproject.toml                     # Python dependencies (pytest, boto3, requests) & coverage settings
├── server/                            # Server configuration, packwiz metadata & docker-compose
│   ├── docker-compose.yml             # itzg/minecraft-server:java21 + itzg/mc-backup
│   ├── pack.toml                      # Packwiz root manifest (MC 1.21.1, Fabric 0.19.3)
│   ├── index.toml                     # Packwiz file index
│   ├── mods/                          # 200+ .pw.toml mod definitions
│   ├── config/                        # Tracked base configuration overrides
│   ├── datapacks/                     # Cobbleverse custom datapacks
│   └── showdown/                      # Node.js Pokemon Showdown battle engine
├── src/mc_server_tools/               # Python cloud & modpack automation package
└── tests/                             # Pytest suite with strict 100% line & branch coverage
```

---

## Quickstart

### 1. Developer Setup (Python & UV)
```bash
# Install dependencies into virtualenv
python -m uv sync --all-extras

# Run full test suite with 100% coverage check
python -m uv run pytest --cov=src --cov=cicd --cov-fail-under=100
```

### 2. Modpack Validation & Local Build
```bash
# Validate modpack manifest and side tagging
python -m uv run python -m mc_server_tools.modpack_builder --validate

# Export Modrinth .mrpack package
python -m uv run python -m mc_server_tools.modpack_builder --export Cobblemon-Modpack.mrpack
```

### 3. Releasing Updates to Discord and Cloud
```bash
git add .
git commit -m "Update Cobblemon mods & balancing"
git tag v1.0.1
git push origin main --tags
```

---

## Documentation

* [AWS Compute Setup Guide](docs/AWS_COMPUTE_SETUP.md)
* [Cloudflare R2 Storage Setup Guide](docs/CLOUDFLARE_STORAGE_SETUP.md)
* [Modpack Administration Guide](docs/MODPACK_ADMIN_GUIDE.md)
* [Player Installation Guide](docs/PLAYER_INSTALLATION_GUIDE.md)
