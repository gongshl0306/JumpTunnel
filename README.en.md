# JumpTunnel — SSH Port Forwarding Tool

English | **[中文](./README.md)**

> A GUI tool that maps internal-network server ports to your local machine through an SSH jump host — so you can reach them straight from your browser or terminal. Think of it as managing several `ssh -N -L ...` commands at once, but with no commands to memorize, no passwords to type, and a clean visual interface.

![Screenshot](./docs/preview.png)

---

## What does this tool do?

In many companies, servers live on an internal network (e.g. `172.17.x.x`) that your laptop can't reach directly. You first SSH into a **jump host** (bastion), and from there access the internal machines.

The classic way is to open a terminal and type:

```bash
ssh -N -L 10011:172.17.12.22:443 tj
```

This means: through jump host `tj`, map the internal `172.17.12.22:443` to your local port `10011`. Then visiting `https://localhost:10011` in a browser is the same as reaching that internal machine.

**The problem**: the command is hard to remember, you can only run one per terminal, you have to type the password every time, ports collide, and you end up with a pile of terminal windows you can't tell apart.

**This tool automates all of that**: fill in a few fields, click a button, and manage many mappings at once.

---

## Who is it for?

- **Ops / backend developers** who routinely access internal web consoles, databases, caches, and SSH terminals through a jump host.
- **QA / frontend developers** who want to open an internal test environment directly in their local browser for debugging.
- **Anyone who doesn't want to memorize SSH flags** like `-L` and `-N` — just click around a GUI.

---

## Key features

| Feature | Description |
|---------|-------------|
| 🔌 **One-click forwarding** | Fill in the jump host and target, click "Start" — password login is handled automatically, no commands needed. |
| 🔢 **Auto port allocation** | Let the OS pick a free local port (no conflicts), or specify one manually. |
| 🌐 **Web ports** (http/https) | Generates a clickable local URL — one click opens it in your browser. |
| 🖥️ **Non-web ports** (ssh/mysql/redis…) | Auto-generates the matching connection command (e.g. `ssh root@localhost -p 10022`), copy it to your clipboard in one click. |
| 💾 **Jump-host profiles** | Save commonly used jump hosts as profiles and switch via dropdown — no re-typing. |
| 📋 **Multi-mapping management** | Each mapping starts/stops independently with a clear status light (🟢running / ⚪stopped / 🔴error). |
| 🔄 **Persistent config** | Restores your last jump host and mapping list after restarting. |

---

## Quick start

### Option 1: Use the prebuilt exe (easiest — nothing to install)

Get `JumpTunnel.exe` and **double-click to run**.

> The first launch is 1–2 seconds slower (a single-file exe has to self-extract). This is normal.

### Option 2: Run with uv (recommended for development)

First install [uv](https://docs.astral.sh/uv/), then:

```bash
uv sync          # create a venv and install dependencies
uv run main.py   # launch the app
```

### Option 3: Traditional pip

Requires Python 3.10+.

```bash
pip install -r requirements.txt
python main.py
```

You can also just double-click `run.bat` (it installs deps and launches).

---

## How to use it

1. **Configure the jump host**
   In the top "Jump host" section, enter the host, port, username, and password.
   Click "Save as new profile" to store it — next time, switch with the dropdown.
   Not sure it connects? Hit "Test connection" first.

2. **Add a mapping**
   In "New mapping", fill in the target IP and target port (the protocol is auto-detected), then click "+ Add mapping".
   - Check "Auto port" to let the system pick a local port (recommended), or uncheck and specify one.
   - A note is optional but handy for telling machines apart.

3. **Start and use**
   In the "Active mappings" list, click "Start" on each row. Once the light turns green:
   - **Web protocol**: click the URL or the "Open" button — your browser opens the local address.
   - **tcp protocol** (ssh/mysql/redis…): click "Copy" to grab the connection command, then paste it into a terminal.

---

## Auto protocol detection

When you type a target port, the protocol is chosen automatically:

| Target port | Protocol chosen | What you get |
|-------------|----------------|--------------|
| 443 / 8443 | https | `https://localhost:<port>` (open in browser) |
| 80 / 8080 / 8000 | http | `http://localhost:<port>` (open in browser) |
| 22 | ssh | `ssh <user>@localhost -p <port>` (copy command) |
| 3306 | mysql | `mysql -h localhost -P <port> -u root -p` (copy command) |
| 6379 | redis | `redis-cli -h localhost -p <port>` (copy command) |
| 5432 | postgres | `psql -h localhost -p <port> -U postgres` (copy command) |
| other | tcp (generic) | `localhost:<port>` (copy connection string) |

> You can also change the protocol manually from the dropdown.

---

## Where is the config stored?

All configuration (jump-host profiles, mapping list) is saved locally:

- **Windows**: `C:\Users\<your-username>\.ssh_forward_tool\config.json`

⚠️ **Security note**: the jump-host password is stored in **plaintext** in this file (so it can be auto-restored).
Make sure the file isn't readable by others. If you'd rather not store it, clear the `password` field manually — but you'll need to re-enter the password each launch.

---

## Build an exe (to distribute)

The `build.spec` is already configured. Recommended via the uv environment:

```bash
# 1. Prepare the environment (first time)
uv sync

# 2. Build
uv run pyinstaller build.spec --noconfirm
```

When done, the single-file exe is at:

```
dist/JumpTunnel.exe
```

About 15MB — **copy it to anyone and they can double-click to run it, no Python needed**.

You can also just double-click `build.bat` in the project to do all of the above in one go.

---

## Project structure

```
main.py              # GUI and entry point
tunnel_manager.py    # SSH tunnel wrapper (built on sshtunnel)
config_store.py      # Local storage for profiles and mappings
pyproject.toml       # uv / dependencies and build config
requirements.txt     # Dependency list for traditional pip
build.spec           # PyInstaller build config
run.bat              # Windows one-click launcher
build.bat            # Windows one-click build script
docs/preview.png     # Product screenshot
```

---

## FAQ

**Q: Tunnel fails with "Authentication failed"?**
A: Check the jump-host username and password — use "Test connection" to verify.

**Q: Local port is already in use?**
A: Check "Auto port" to let the system allocate one, or pick a free port number.

**Q: Tunnel is up but the target is unreachable?**
A: Make sure the target IP and port are actually reachable from the jump host (SSH in and ping/curl it).

**Q: It's a non-web port like SSH — how do I use it?**
A: Click "Copy" to get the connection command (e.g. `ssh root@localhost -p 10022`), then paste it into a terminal.

---

## Technical notes

- GUI built with Python + [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter).
- SSH password login and port forwarding done in code via [sshtunnel](https://github.com/pahaz/sshtunnel) (on top of paramiko).
  Windows' built-in `ssh.exe` doesn't accept a plaintext password on the command line and this machine has no `plink`, so a library approach is used for reliable password auth.
- Auto port allocation works by binding local port `0`, letting the OS assign a free port; the actual port is read back after the tunnel starts.

---

English | **[中文](./README.md)**
