# 🛡️ GateKeeper CLI

**A Zero-Trust Pre-Publish Firewall for Developers.**

GateKeeper intercepts your `git push` and `npm publish` commands to prevent catastrophic IP leaks and secret exposure *before your code ever leaves your hard drive.*

GateKeeper operates on a **True Zero-Trust Architecture**: instead of relying on brittle `.gitignore` blocklists, it treats *every single file* as strictly private by default. You must explicitly whitelist files to allow them to leave your machine.

---

## 🚀 Quick Start

### 1. Install

```bash
pip install gatekeeper-cli
```

### 2. Inject Shell Shims (One-Time, Global Setup)

This intercepts `git push` and `npm publish` in any terminal you open — forever.

```bash
gatekeeper install
```

Supports **Bash**, **Zsh**, and **PowerShell**. Once installed, source your profile or open a new terminal:

```bash
# Bash / Zsh
source ~/.bashrc   # or ~/.zshrc

# PowerShell (run in new window, or:)
. $PROFILE
```

### 3. Initialize a Project

Navigate into any repository and run:

```bash
cd my-secret-project/
gatekeeper init
```

You will be prompted to choose a protection mode:

| Option | Mode | Behavior |
|--------|------|----------|
| **1** | Open-Source | All files explicitly allowed to publish |
| **2** | Private App | Complete lockdown — nothing can leave |
| **3** | Mixed | Opens the Interactive File Vault UI |

### 4. The Interactive File Vault (Mixed Mode)

A full-screen terminal UI opens, showing your entire project directory tree. Every file starts as `🔴 PRIVATE`.

| Key | Action |
|-----|--------|
| `↑ / ↓` | Navigate the tree |
| `Space` | Toggle file or folder between 🔴 PRIVATE / 🟢 PUBLIC |
| `S` | Save & lock the vault |

Toggling a **parent folder** recursively marks all its children as public or private — a single keypress protects an entire subtree.

### 5. Work Normally

GateKeeper runs silently in the background. Keep working as usual:

```bash
git add .
git commit -m "feat: new feature"
git push
```

The moment you hit `Enter`, GateKeeper intercepts the push and runs a **3-stage evaluation pipeline** automatically.

---

## 🔍 The 3-Stage Evaluation Pipeline

Every `git push` or `npm publish` is evaluated in real-time through three sequential safety gates:

### Stage 0 — Bloat Guard

Before even loading your whitelist, GateKeeper checks if you accidentally committed massive dependency folders:

**Blocked directories:** `venv/`, `.venv/`, `node_modules/`, `__pycache__/`, `dist/`, `.env/`

If detected, GateKeeper offers to:
- Automatically run `git rm --cached` to un-commit the bloat
- Amend your last commit in-place (`git commit --amend --no-edit`)
- Append the directory to your `.gitignore` permanently

### Stage 1 — IP Vault Check

Validates every file in the outgoing payload against your whitelist. Two sub-checks run in order:

**Hard-Ban Filenames** (always blocked, regardless of whitelist):

| Filename | Reason |
|----------|--------|
| `.env`, `.env.local`, `.env.production` | Environment secrets |
| `secrets.json`, `secrets.yaml`, `credentials.json` | Credential stores |
| `serviceaccountkey.json`, `firebase-adminsdk.json` | Cloud service accounts |
| `id_rsa`, `id_ed25519`, `id_ecdsa` | Raw SSH private keys |
| `.htpasswd`, `wp-config.php` | Web server credentials |

**Hard-Ban Extensions** (always blocked):

`.map` · `.env` · `.pem` · `.key` · `.log` · `.p8`

**Whitelist Resolution** — Uses longest-prefix matching with explicit deny support:
- Whitelisted paths allow all files under that path
- Explicitly denied paths override parent whitelists
- The most specific (longest) match wins

If private files are found in the payload, GateKeeper asks if you want to **automatically strip them** from the commit (`git rm --cached` + `git commit --amend`) so your push can proceed with only the safe files.

### Stage 2 — Deep Secret Scan (Powered by Gitleaks)

All whitelisted, outgoing files are run through [Gitleaks](https://github.com/gitleaks/gitleaks) — an enterprise-grade secret detection engine — before the push is released.

**What it detects:**
- OpenAI, Anthropic, Cohere API Keys
- AWS Access Keys & Secret Keys
- GitHub, GitLab, Bitbucket tokens
- Stripe, Twilio, SendGrid API Keys
- Google Cloud, Firebase credentials
- Raw RSA/DSA/ECDSA PEM blocks
- JWT tokens
- Generic high-entropy secret patterns
- 20+ additional provider patterns

**Memory-safe scanning:**
- Files larger than **5 MB** are automatically skipped (prevents OOM on binary assets)
- Gitleaks is downloaded on first use and cached at `~/.gatekeeper/bin/gitleaks`
- SHA-256 checksum verification is performed on the downloaded binary to guard against MITM attacks

---

## 🔒 Architecture Deep Dive

### Shell Shim Interception

`gatekeeper install` injects thin wrapper functions into your shell profile that transparently replace `git` and `npm`:

**Bash / Zsh** (`~/.bashrc` or `~/.zshrc`):
```bash
git() {
    if [[ "$1" == "push" ]]; then
        gatekeeper check git-push && command git "$@"
    else
        command git "$@"
    fi
}
```

**PowerShell** (`$PROFILE`):
```powershell
function git {
    if ($args[0] -eq "push") {
        gatekeeper check git-push
        if ($LASTEXITCODE -eq 0) { & "git.exe" @args }
    } else { & "git.exe" @args }
}
```

All other git/npm commands pass through to the real binary unmodified.

### Git Pre-Push Hook (GUI Client Protection)

`gatekeeper init` also installs a `.git/hooks/pre-push` hook automatically. This means **GUI-based Git clients** (VS Code Source Control, GitHub Desktop, Tower, Sourcetree, etc.) are **also protected**, even if they bypass your shell shims.

```sh
#!/bin/sh
# >>> GateKeeper Hook >>>
gatekeeper check git-push --non-interactive
if [ $? -ne 0 ]; then
    exit 1
fi
# <<< GateKeeper Hook <<<
```

### Clearance Token (Anti-Double-Invocation)

When the interactive shell shim runs and passes all checks, it writes a **clearance token** to `~/.gatekeeper/push_cleared_at` containing the current Unix timestamp.

The pre-push Git hook (which fires milliseconds later) reads this token: if it was written **within the last 60 seconds**, the hook skips its own full re-evaluation and exits 0 immediately, then deletes the token so it cannot be reused.

This prevents the double-invocation loop that would otherwise occur when both the shell function and the git hook fire for the same push.

### `.gatekeeper.json` Config File

Each initialized project stores its whitelist config in `.gatekeeper.json` at the project root. This file should be committed to source control — it is your repository's security policy.

Format:
```json
{
  "whitelist": ["src", "README.md", "pyproject.toml"],
  "blacklist": ["src/secrets"]
}
```

---

## 🛠️ CLI Reference

```
gatekeeper --help
```

### `gatekeeper install`
Injects shell shims into your terminal profile to intercept `git push` and `npm publish` globally. Prompts you to choose Bash/Zsh or PowerShell. Safe to run multiple times — detects and skips if already installed.

### `gatekeeper init`
Initializes GateKeeper in the current directory. Analyzes the project, creates `.gatekeeper.json`, and installs the `.git/hooks/pre-push` hook. Also auto-creates a `.gitignore` seeded with standard ignores if one doesn't exist.

### `gatekeeper check <command>`
Manually trigger the evaluation pipeline. Used internally by shell shims and git hooks.

```bash
gatekeeper check git-push          # Interactive mode
gatekeeper check git-push --non-interactive  # CI / git hook mode
gatekeeper check npm-publish       # npm tarball evaluation
```

---

## 📁 What Happens on First Push (No Config)

If you run `git push` in a repo that has **no `.gatekeeper.json`**, GateKeeper still runs the Bloat Guard (Stage 0) and then prompts you:

```
🚨 No GateKeeper Security Firewall detected in this repository!
Do you want to:
  [1] Initialize GateKeeper now
  [2] Push Unprotected (Bypass Firewall)
  [3] Abort Push
```

This ensures you always have a safety net, even in repos you haven't explicitly configured.

---

## 🤖 CI / Non-Interactive Mode

In CI environments (GitHub Actions, Jenkins, etc.) or when called by the git hook, GateKeeper automatically switches to `--non-interactive` mode when `stdin` is not a TTY. In this mode:

- Bloat detected → **abort** (no prompt to fix)
- Private files in payload → **abort** (no prompt to strip)
- Secrets found → **abort**

There are no prompts and no user intervention required. A non-zero exit code signals the CI pipeline or git hook to fail the operation.

---

## 🔧 Requirements

| Requirement | Version |
|-------------|---------|
| Python | ≥ 3.8 |
| typer | ≥ 0.9.0 |
| rich | ≥ 13.0.0 |
| textual | ≥ 0.40.0 |
| Gitleaks | Auto-downloaded on first use (v8.18.2) |

Gitleaks supports **Windows (x64/arm64)**, **macOS (x64/arm64)**, and **Linux (x64/arm64/armv7)** and is automatically downloaded and cached on first secret scan.

---

## 🌐 npm Publish Protection

GateKeeper also intercepts `npm publish`. It uses `npm pack --dry-run --json` to extract the **exact file list** that would be included in the tarball — then runs that list through the same 3-stage pipeline.

If private files are found, GateKeeper offers to append them to `.npmignore` automatically so the publish can proceed with only the safe files.

---

## ⚡ Performance Notes

- **Null-byte sniffing**: Binary files are detected and skipped before Gitleaks is invoked, preventing OOM on large video/PDF assets.
- **File size cap**: Files > 5 MB are skipped by the secret scanner.
- **Per-file scanning**: Each file is scanned independently, not the entire repo, for precision and speed.
- **Cached binary**: Gitleaks is downloaded once and cached at `~/.gatekeeper/bin/` — subsequent pushes add zero download latency.
- **Checksum verification**: The Gitleaks binary is verified against the official `checksums.txt` from GitHub Releases using SHA-256 before extraction.

---

## 🤝 Contributing

Pull requests are welcome! Please open an issue first to discuss what you'd like to change.

```bash
git clone https://github.com/gijendrap/gatekeeper
cd gatekeeper
pip install -e ".[dev]"
pytest
```

---

## 📄 License

MIT © [Gijendra](https://github.com/gijendrap)

---

<p align="center">
  Built to stop the next leak before it happens.
</p>
