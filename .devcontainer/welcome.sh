#!/usr/bin/env bash
# Printed every time the sandbox machine starts. Node + Python + git are already
# here (the gates need Node + Python). This does NOT log you in; device-flow
# login needs you to see a code and approve it, so you run init yourself below.
cat <<'BANNER'

=====================================================================
  TruVerifAI Panel Review, evaluation sandbox
=====================================================================
  This is a disposable machine in YOUR tenancy. Deleting it removes
  everything (uninstall = the machine ceasing to exist).

  STEP 1: install your coding agent and sign in with YOUR OWN account
    (Claude Code / Codex / Cursor / Copilot / Gemini / Antigravity;
    install the one your team uses, init arms whichever it finds).
    e.g.  npm install -g @anthropic-ai/claude-code   then   claude

  STEP 2: arm the review gates (one command):
      npx @truverifai/init
    It prints a code + a truverif.ai URL and waits. Open that URL in
    your browser, approve, and the gates arm on this machine. (No
    browser opens here, you approve in your own browser, TV-style.)
    Your first login is granted free evaluation credits automatically.

  STEP 3: watch a gate block a risky change in under a minute:
      npm run demo:risky-change
    then:  git add -A && git commit -m "widen position cap"
    The commit gate should STOP it and cite the trade-core floor.

  Full walkthrough + "things to try":  README.md  /  THINGS-TO-TRY.md
  Prefer your own models / no data stored? see README "Data control".
=====================================================================

BANNER
