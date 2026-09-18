# Things to try

Five things, ~10 minutes. The point is to see the gate tell the difference
between changes that matter and changes that don't, a quiet gate on a safe
change is the product working, not broken.

| # | Do this | What should happen |
|---|---|---|
| 1 | `npm run demo:risky-change` then `git add -A && git commit -m x` | **Blocked.** The commit gate stops it, cites the `trade_core` / `risk_limits` floor, routes it to a review. |
| 2 | Ask your agent to remove a stop-loss or risk check in `demo/tradecore.py`, then commit | **Blocked / reviewed.** A removed guard in floored code is exactly what must not ship unreviewed. |
| 3 | Edit a comment or a log string anywhere, then commit | **Silent.** Safe changes sail through, the gate isn't just blocking everything. |
| 4 | Ask your agent to add `self.Liquidate()` with no condition, then commit | **Blocked / flagged.** A destructive, unconditional action gets caught. |
| 5 | Make a risky edit, run the review the gate points you to (`audit_coding`), apply findings, commit | **Proceeds**, you see the review → fix → ship loop, and that a real panel changed the outcome. |

Also worth seeing:
- **`npx @truverifai/init doctor`**, proves the gates are actually armed (green rows), not just installed.
- **Commit outside your agent**, make a risky change by hand and `git commit`; the **git pre-commit gate** still blocks it, no agent involved.
- **Your own floors**, edit `.truverifai/risk.json` to mark a file *you* care about, then change that file and watch it fire. Validate with `npx @truverifai/init floors check --preview`.
- **Your own code**, drop a non-critical repo of yours in here and build on it for a day. Real verdicts on code you understand.

Four outcomes you should be able to tell apart by the end: **blocked by policy**,
**safe change approved**, **out of credits** (top-up is on us: email us your
login), and **gate genuinely armed** (`doctor` green).
