# 🛡️ GateKeeper CLI

**A Zero-Trust Pre-Publish Firewall for Developers.**  
GateKeeper intercepts your `git push` and `npm publish` commands to prevent catastrophic IP or API Secret leaks *before* your code ever leaves your hard drive.

Built to prevent incidents like the [Anthropic Claude Code Leak](https://www.theverge.com/2024), GateKeeper operates on a **True Zero-Trust Architecture**. Instead of relying on brittle `.gitignore` blocklists, GateKeeper treats *every single file* as strictly private. You must explicitly whitelist files to allow them to leave your local machine.

---

## 🚀 Quick Start Guide

### 1. Global Installation
Install GateKeeper globally on your machine using Python'sss package manager:
```bash
pip install gatekeeper-cli
```

### 2. Shell Injection (One-Time Setup)
To allow GateKeeper to automatically protect your terminal, you must install the shell shims. This safely intercepts `git` and `npm` commands directly in your active terminal.
```bash
gatekeeper install
```
*(Supports Bash, Zsh, and PowerShell).*

### 3. Initialize a Project 
Navigate into any code repository you want to protect and initialize the firewall:
```bash
cd my-secret-project/
gatekeeper init
```
You will be prompted to classify the repository:
- **[1] Open-Source:** Entire repository explicitly allowed to publish.
- **[2] Private App:** Complete lockdown. Nothing is allowed to leave.
- **[3] Mixed (Selective Publishing):** Opens the Interactive Terminal UI.

### 4. The Interactive UI
If you select **Mixed**, an interactive Tree UI will open tracking your local directory. 
- All files start as `[🔴 PRIVATE]`.
- Press `Spacebar` to explicitly mark files or parent folders as `[🟢 PUBLIC]`.
- Press `S` to save and lock the vault.

### 5. Work as Normal!
You no longer need to remember GateKeeper exists. Keep working normally:
```bash
git add .
git commit -m "added new features"
git push
```
The moment you hit `Enter`, GateKeeper will intercept the push:
1. **IP Vault Check:** Identifies if any private files are sneaking into the payload. If triggered, it can dynamically auto-amend your Git history to strip the private files out safely!
2. **Deep Secret Scan:** Scans all *Public* outgoing files against an Enterprise-grade dictionary of 20+ API Keys (OpenAI, AWS, Stripe, GitHub, Cloud Storage URLs, raw RSA Key blocks, etc.)
3. **Execution:** If safe, the `git push` is released to the server!

---

## 🔒 Advanced Secret Engine
GateKeeper does not blindly decode giant `.mp4` or `.pdf` files. It utilizes native `b"\0"` null-byte sniffing to achieve massive concurrency over text files while avoiding Python Out-Of-Memory exceptions on 1GB+ JSON files. It natively halts memory-intense regex parsing in `0.02ms`.
