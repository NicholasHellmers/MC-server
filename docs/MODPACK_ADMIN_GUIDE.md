# Modpack Administration & Development Guide

This guide outlines the standard GitOps development cycle for modifying mods, updating configs, testing locally, and releasing updates to players and the production cloud server.

---

## The 3-Step Daily Workflow

```
1. Pull Latest  ───►  2. Edit & Test Locally  ───►  3. Commit, Tag & Push
```

---

### Step 1: Pull Latest Version
```bash
git pull origin main
```

---

### Step 2: Adding / Updating Mods Locally

#### Adding a Mod
To add a new mod from Modrinth:
```bash
packwiz mr add <mod-slug>
```
*Example:*
```bash
packwiz mr add toms-storage
```
*Packwiz automatically resolves dependencies (Fabric API, Architectury, Cloth Config) and creates the `.pw.toml` definition.*

#### Updating All Mods
To update all mods to the latest compatible versions for Minecraft 1.21.1:
```bash
packwiz update --all
```

#### Modifying Configs & Datapacks
* Edit configs directly inside `server/config/`.
* Edit custom Cobbleverse datapacks in `server/datapacks/`.

#### Validating the Modpack
Run the modpack validator to verify that all hashes, URLs, and side classifications are consistent:
```bash
uv run python -m mc_server_tools.modpack_builder --validate
```

#### Smoke Testing the Server (Headless Check)
Verify that the server configuration boots cleanly without mixin crashes:
```bash
uv run python -m mc_server_tools.modpack_builder --test-server
```

---

### Step 3: Releasing to Discord and Deploying to Cloud

Once your local changes are tested and verified, release a new version with a single command:

```bash
git add .
git commit -m "Add Tom's Storage and rebalance Cobblemon spawn rates"
git tag v1.0.1
git push origin main --tags
```

#### What Happens Automatically in GitHub Actions:
1. **100% Code Coverage Suite**: Runs and verifies all tests pass.
2. **Export `.mrpack`**: Generates `Cobblemon-Modpack-v1.0.1.mrpack`.
3. **GitHub Release**: Attaches the `.mrpack` archive to a new GitHub release.
4. **Discord Announcement**: Posts an embed notification in your Discord server with the download link and changelog.
5. **Server Rolling Update**: Connects via SSH to your AWS server, syncs the repository, and restarts the Minecraft container with the new mods while **preserving the live world save and player data**.
