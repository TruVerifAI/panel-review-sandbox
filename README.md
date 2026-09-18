# Panel Review: evaluation sandbox

A **disposable machine in your own tenancy**, pre-set-up so you can see
TruVerifAI Panel Review's review gates block a risky change in about a minute, 
without installing anything on a real laptop and without your code touching our
servers. When you're done, delete the machine and nothing remains.

> **What leaves this machine:** only the diff you submit for review. The local
> gates send hashes + labels, never your source. You can turn even that off, or
> run the review on your own models, see **Data control** below and
> `SECURITY.md`.

---

## Run it: two ways

**A) GitHub Codespaces (one click).** Click **"Use this template"** (top of this
repo) → create your own copy → **Code ▸ Codespaces ▸ Create codespace**. A
browser editor opens in ~a minute. Everything below runs in its terminal.

**B) Your own AWS / VM (no GitHub Codespaces needed).** On any machine with
**Node 18+, Python 3, and git** (an EC2 box, your laptop, any Docker host): clone
your copy of this repo and follow the same steps. Codespaces is just the
easy button, the gates only need Node + Python + git.

## Step 1: arm the review gates

```
npx @truverifai/init
```
It prints a short code + a `truverif.ai` URL and waits. Open that URL in your
browser, approve, and the gates arm on this machine. (No browser opens on the
machine, you approve in your own browser, the way you sign a TV into a
streaming app.) Your first login is granted **free evaluation credits**
automatically.

`init` detects and arms **every coding agent it finds** on the machine, plus a
git pre-commit gate for this repo. Confirm it's live:
```
npx @truverifai/init doctor
```

## Step 2: sign in your coding agent (your own account)

Use whichever agent your team uses, the gates work the same on all of them.
Bring your **own** agent login (we don't fund agent sessions):

- **Claude Code**, `claude` (sign in when prompted). The richest integration:
  write gate + commit gate, native.
- **Codex CLI**, `codex` (choose **Trust** if it asks about hooks).
- **Cursor CLI**, **GitHub Copilot CLI**, **Gemini CLI**, **Antigravity**, all
  supported; sign in with your account. (`init` already wrote their gate config.)

Not all agents are pre-installed in the sandbox, install the one you want, then
re-run `npx @truverifai/init` so its gate is armed.

## Step 3: watch a gate block a risky change

```
npm run demo:risky-change
git add -A && git commit -m "widen position cap"
```
The demo widens the position-size cap in the trade core (`demo/tradecore.py`), 
exactly the kind of change that must never ship unreviewed. The **commit gate
stops it**, cites the `trade_core` / `risk_limits` floor you own (see
`.truverifai/risk.json`), and routes it to a review. That's the product in one
motion.

Then try the rest: **`THINGS-TO-TRY.md`**.

## Bring your own code

The demo (`demo/`) is throwaway trading code, not ours, doesn't run, safe to
break. The real test: drop **any non-critical repo of your own** in here and
build features on it for days with your agent. You'll get real verdicts on code
you understand. Your code stays in this machine (your tenancy); only the diffs
you submit for review reach our API.

Mark **your** important code with custom floors, edit `.truverifai/risk.json`
(or ask your agent: "set up custom floors for this repo") and validate with
`npx @truverifai/init floors check --preview`.

## Data control: you choose how much reaches us

Signed in with the same login, on truverif.ai you can:
- **Turn off content persistence** (settings ▸ MCP ▸ "Decide on data
  persistence"), review content is then not stored our side (billing/usage
  metadata still is). Default is ON, which gives you a dashboard audit trail of
  the eval; your call.
- **BYOK**, use your own model-provider keys.
- **BYOM**, run the panel on **your own models in your own AWS/GCP** so review
  content never reaches our model accounts. Ideal if you already run inference.

See `SECURITY.md` for the full data-flow.

## When you're done: teardown

```
npx @truverifai/init uninstall
```
Removes the gates and **revokes your API key server-side** (a leaked copy is
dead). Then delete the Codespace (or your VM), the machine and everything on it
is gone. Uninstall = the machine ceasing to exist.

---

*The entire client is open source, MIT, zero runtime dependencies:
`github.com/TruVerifAI/init`. Read every line before you trust it.*
