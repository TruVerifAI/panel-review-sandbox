# Panel Review: evaluation sandbox

A **disposable machine in your own tenancy**, pre-set-up so you can see
TruVerifAI Panel Review's review gates block a risky change in about a minute,
without installing anything on a real laptop and without your code touching our
servers. When you're done, delete the machine and nothing remains. Budget about
fifteen minutes end to end.

> **What leaves this machine:** only the diff you submit for review. The local
> gates send hashes + labels, never your source. You can turn even that off, or
> run the review on your own models, see **Data control** below and
> `SECURITY.md`.

**Two accounts are involved, both used on this machine:**
- **Your coding-agent account** (for example your Claude Code login), to sign the
  agent in.
- **Your TruVerifAI account**, used by `npx @truverifai/init` to arm the gates and
  grant evaluation credits. The same login later unlocks BYOK / BYOM /
  persistence on truverif.ai.

---

## Step 1: open the machine

You need a Linux machine with **Node 18+, Python 3, and git**. Pick one path.

**A) GitHub Codespaces (one click, nothing to provision).**
1. Click **"Use this template" ▸ Create a new repository** (top of this repo) to
   make your own copy.
2. In your copy, click **Code ▸ Codespaces ▸ Create codespace on main**.
3. A browser VS Code opens in about a minute. Node, Python, and git are already
   here, and a welcome banner prints the steps. Everything below runs in its
   terminal.

**B) Your own AWS EC2 (or any VM / Docker host).** On a fresh instance:
1. **Launch an instance.** Amazon Linux 2023 or Ubuntu 22.04+, a small size is
   plenty (`t3.small`, 2 vCPU / 2 GB). Open only SSH (port 22) to your own IP; no
   inbound web ports are needed.
2. **SSH in**, then install the toolchain:
   ```
   # Ubuntu:
   sudo apt update && sudo apt install -y git python3 curl
   curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
   sudo apt install -y nodejs

   # Amazon Linux 2023:
   sudo dnf install -y git python3 nodejs20
   ```
3. **Get your copy.** Use "Use this template" as in Path A, then clone it (so your
   commits are yours):
   ```
   git clone https://github.com/<your-org>/<your-sandbox-copy>.git
   cd <your-sandbox-copy>
   npm install
   ```
Confirm the toolchain: `node -v` (18+), `python3 --version` (3.x), `git --version`.

## Step 2: install your coding agent and sign in (your own account)

`init` arms the gates on whatever agents are already installed on this machine
(it finds them by their CLI on the PATH), so install the agent you'll use here
and sign in with your **own** agent account first. For example, Claude Code:
```
npm install -g @anthropic-ai/claude-code
claude      # sign in with your company Claude account when prompted
```
Any certified agent works the same way, the gates behave the same on all of
them:
- **Claude Code** (`claude`), the richest integration: write gate + commit gate,
  native.
- **Codex CLI** (`codex`), choose **Trust** if it asks about hooks.
- **Cursor CLI**, **GitHub Copilot CLI**, **Gemini CLI**, **Antigravity**, all
  supported; install and sign in with your account.

Install the one your team uses (you don't need all of them). We don't fund agent
sessions, bring your own login.

## Step 3: arm the review gates

```
npx @truverifai/init
```
It detects your agent from Step 2, then signs you in to TruVerifAI by device
flow: it prints a short code + a `truverif.ai` URL and waits. Open that URL in
your own browser, enter the code, and approve. (No browser opens on the machine,
you approve in your own browser, the way you sign a TV into a streaming app.)
Your first login is granted **free evaluation credits** automatically.

`init` then installs the write gate + commit gate on your agent, plus a git
pre-commit gate for this repo. Confirm it's live (it fires a synthetic gate to
prove it, not just checks that files exist):
```
npx @truverifai/init doctor
```
Green rows mean armed. Installed another agent since? Re-run
`npx @truverifai/init` to arm it too. Full per-agent setup:
**truverif.ai/settings/mcp**.

## Step 4: watch a gate block a risky change

```
npm run demo:risky-change
git add -A && git commit -m "widen position cap"
```
The demo stages a change that warrants panel review: it widens the position-size
cap in the trade core (`demo/tradecore.py`). The **commit gate stops it**, cites
the `trade_core` / `risk_limits` floor you own (see `.truverifai/risk.json`), and
routes it to a review. That's the product in one motion. To undo the edit, revert
the file with git (`git checkout -- demo/tradecore.py`).

Then try the rest: **`THINGS-TO-TRY.md`**.

## Step 5: bring your own code and floors

The demo (`demo/`) is throwaway trading code, not ours, doesn't run, safe to
break. The real test: drop **any non-critical repo of your own** onto the machine
and build features on it for days with your agent. You'll get real verdicts on
code you understand, and it never leaves your tenancy; only the diffs you submit
for review reach our API.

To make the gate treat **your** important files as must-review, set up custom
floors:
1. **Scaffold and draft.** Run `npx @truverifai/init floors init`. It creates an
   inert `.truverifai/risk.json` and prints a prompt you can hand your agent to
   draft real floors for the repo. (Or just ask your agent: "set up custom floors
   for this repo.")
2. **Validate coverage.** Run `npx @truverifai/init floors check --preview`. It
   shows exactly which files each floor covers, so you can confirm you fenced the
   right code.
3. **See it fire.** Change a floored file and commit, the gate blocks and cites
   your own floor by name.

## Data control: you choose how much reaches us

Signed in to truverif.ai with the **same TruVerifAI account** from Step 3:
- **Content persistence.** ON by default (a dashboard audit trail of your eval).
  Turn it **off** at **truverif.ai/settings/mcp** and review content is no longer
  stored our side (only usage/billing metadata is). Your choice.
- **BYOK, bring your own keys.** Run the review on your own model-provider keys.
  Set it up at **truverif.ai/byok**.
- **BYOM, bring your own models.** Run the whole panel on **your own models in
  your own AWS Bedrock or GCP Vertex tenancy**, so review content never reaches
  our accounts. Best if you already run inference. Details at
  **truverif.ai/byom**.

See `SECURITY.md` for the full data-flow.

## When you're done: teardown

```
npx @truverifai/init uninstall
```
Removes the gates and **revokes your API key server-side** (a leaked copy is
dead). Then delete the Codespace (or terminate the EC2 instance), the machine and
everything on it is gone. Uninstall = the machine ceasing to exist.

## Cost and credits

Compute only, often **$0** on the Codespaces free tier, and single-digit to
low-tens of dollars for a multi-day eval on Codespaces or a small EC2 box. The
review **credits are on us** for the evaluation: your first login gets 50 free,
and if you need more, email us the login you used and we top you up.

---

*The entire client is open source, MIT, zero runtime dependencies:
`github.com/TruVerifAI/init`. Read every line before you trust it.*
