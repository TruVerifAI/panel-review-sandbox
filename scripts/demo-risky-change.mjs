// Deterministic demo trigger, you don't have to invent a risky prompt.
// It widens the position-size risk cap in the trade core (0.08 -> 1.00),
// exactly the kind of change that must never ship unreviewed. Then you commit
// it and watch the gate block it and cite the trade-core floor.
import { readFileSync, writeFileSync } from "node:fs";

const FILE = "demo/tradecore.py";
const FROM = "MAX_POS_PCT = 0.08";
const TO = "MAX_POS_PCT = 1.00";

let src;
try {
  src = readFileSync(FILE, "utf8");
} catch {
  console.error(`Could not read ${FILE}, run this from the repo root.`);
  process.exit(1);
}

if (!src.includes(FROM)) {
  if (src.includes(TO)) {
    console.log("Already applied (position cap is 1.00). Reset it with git, then re-run.");
  } else {
    console.error(`Marker '${FROM}' not found in ${FILE}. Edit any risk constant by hand instead.`);
    process.exit(1);
  }
} else {
  writeFileSync(FILE, src.replace(FROM, TO));
  console.log("Applied a risky change to the trade core:");
  console.log(`  ${FILE}:  ${FROM}  ->  ${TO}   (removed the 8% notional cap)`);
}

console.log("\nNow commit it and watch the gate block it:");
console.log('  git add -A && git commit -m "widen position cap"');
console.log("\nExpected: the COMMIT gate denies it, cites the 'trade_core' / 'risk_limits' floor,");
console.log("and routes it to a review. To undo the edit, revert the file with git.");
