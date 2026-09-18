# Panel Review: security & data-flow one-pager

*For an enterprise security / AppSec reviewer deciding whether to run the
disposable sandbox. Every claim below is verifiable against our public client
source (`github.com/TruVerifAI/init`, MIT, zero runtime dependencies), and this
document is the contract: if something here is wrong, tell us and we fix it.*

---

## In one line

Your code stays in your tenancy. Only the specific **diff you submit for
review** leaves your machine; the local gates send **hashes and labels, never
your source**; and you can turn even the diff-storage off, or run the whole
review on **your own models in your own cloud** so it never reaches us at all.

**And you don't have to take our word for it.** Everything this command
installs is open source: MIT-licensed, zero runtime dependencies. Read every
line at github.com/TruVerifAI/init before you trust it.

## What the sandbox is

A disposable machine **in your own tenancy**, a GitHub Codespace in your org,
or your own AWS EC2 / any Docker host, with Panel Review's client-side gates
installed by `npx @truverifai/init`. Deleting the machine removes everything;
uninstall = the machine ceasing to exist. Nothing is installed on a real laptop.

## What leaves the machine, exactly

| Event | What is sent to us | What is NOT sent |
|---|---|---|
| **Gate check** (on a risky write/commit) | a **hashed** repo fingerprint (SHA-256 of the git remote URL or repo path), **content hashes** of the changed hunks, and the local classifier's **category labels + scores** | your source code; your file paths (only coarse class tags like "test/docs"); the raw repo URL/path |
| **Panel review** (`audit_coding` etc.) | only the **diff / context your agent explicitly submits** for that review, that is the product: the change you chose to have reviewed | anything you didn't submit |
| **Update check** | the client's own version string | anything else |
| **Diagnostics** (`TVAI_PAYLOAD_LOG`) | nothing, **local-only and opt-in** |, |

## What is stored, and for how long

- **Persistence ON** (the account default): the submitted review **content** is
  stored (this is what powers your dashboard audit trail) plus usage/billing
  **metadata**. You can delete stored content and revoke access at any time from
  your account.
- **Persistence OFF** (one toggle, your choice, settings → MCP → "Decide on
  data persistence"): review **content is not stored**; only usage/billing
  **metadata** (counts, timestamps, model consensus, verdicts, hashed
  fingerprints) is recorded. "Nothing stored" is precise here as *no content*,
  not *no metadata*.
- Gate-check payloads (hashes + labels) back the admin dashboard row: repo
  fingerprint + category labels + hunk count + a pushed flag, **never a diff,
  path, command text, or commit SHA.**

## The data-control ladder: you choose how much reaches us

1. **Default:** hosted panel (our models), persistence on.
2. **Persistence off:** no review content stored our side.
3. **BYOK (bring your own keys):** the review runs on your own model-provider
   keys.
4. **BYOM (bring your own models):** the panel runs on **your own models in your
   own AWS Bedrock / GCP Vertex tenancy**, review content is processed by the
   models **you already operate** and **never reaches our model accounts**. For
   enterprises that already run their own inference, this is the strongest
   posture and needs no new infrastructure on your side.

All four are self-serve on truverif.ai, keyed to the login you use in the
sandbox.

## Authentication & secrets

- Sign-in is a browser **device-flow**: the CLI never sees a password; it mints
  a per-user API key you approve in your own browser. The key is written only to
  the disposable machine (`~/.truverifai/config.json`).
- The key is **revocable**: `npx @truverifai/init uninstall` revokes it
  server-side (`POST /v1/keys/self/revoke`) before deleting it locally, so a
  leaked copy is dead. You can also revoke any key from your API-keys page.
- No secret is baked into the template repo. The sandbox uses **your** freshly
  minted, self-revocable key, not a shared credential.

## Failure behaviour

The gates **fail open by design**: if our server is unreachable or anything
errors, your commit/write proceeds and a visible notice says the change was not
gated. The tool never blocks your work on its own failure, and never blocks it
on *our* outage.

## What remains after you delete the sandbox

- The disposable machine and everything on it (including the local key file):
  **gone**.
- Server-side: the API key (revoke it, one command, or the API-keys page) and,
  if persistence was on, the stored review content + usage metadata, which you
  can delete from your account. With persistence off, only usage metadata.

## Verify it yourself

The entire client is public and dependency-free:
`npm pack @truverifai/init`, extract, and read `bin/tvai.js`, `lib/*.js`, and
`vendor/gates/*.py`, that's the whole runtime surface. Published with build
provenance attestations. Nothing runs as a service, daemon, or startup item;
the gates run only when your agent host invokes its hooks.
