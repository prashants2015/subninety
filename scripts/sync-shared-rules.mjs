#!/usr/bin/env node
// Shared rules sync (docs/shared-rules-howto.md in prashants2015/nutrition-companion).
// The same file sits in every repo that holds the shared rules; no dependencies.
//
//   node scripts/sync-shared-rules.mjs                  copy the master from GitHub (needs `gh`)
//   node scripts/sync-shared-rules.mjs --from <path>    copy it from a local checkout (folder or file)
//   node scripts/sync-shared-rules.mjs --check          offline: fail if AGENTS.shared.md was hand-edited
//   node scripts/sync-shared-rules.mjs --stamp          master repo only: record the hash after an edit
//
// Every AGENTS.shared.md starts with one header line that ends in
// "master-sha256: <hash>". The hash is of everything after that line. --check
// recomputes it, so a hand edit in a copy (or an unstamped edit in the master)
// fails the repo's verify command without any network.

import { createHash } from "node:crypto";
import { readFileSync, writeFileSync, existsSync, statSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

export const MASTER_REPO = "prashants2015/nutrition-companion";
export const FILE_NAME = "AGENTS.shared.md";
const SCRIPT = "node scripts/sync-shared-rules.mjs";
const HASH_TAG = /master-sha256: ([0-9a-f]{64})\s*$/;

export function bodyHash(body) {
  return createHash("sha256").update(body.replace(/\r\n/g, "\n")).digest("hex");
}

export function masterHeader(hash) {
  return `> **Shared rules: this is the master** (${MASTER_REPO}, \`${FILE_NAME}\`). Edit it here, run \`${SCRIPT} --stamp\`, then run \`${SCRIPT}\` in every repo that holds a copy. master-sha256: ${hash}`;
}

export function copyHeader(hash) {
  return `> **Shared rules, copied from the master** in ${MASTER_REPO} (\`${FILE_NAME}\`). Do not edit here; edit the master and run the sync: \`${SCRIPT}\`. master-sha256: ${hash}`;
}

// → { header, body, recorded, isMaster } or null when there is no header line.
export function split(text) {
  const t = text.replace(/\r\n/g, "\n");
  const nl = t.indexOf("\n");
  const header = nl === -1 ? t : t.slice(0, nl);
  const m = header.match(HASH_TAG);
  if (!m) return null;
  return { header, body: nl === -1 ? "" : t.slice(nl + 1), recorded: m[1], isMaster: header.includes("this is the master") };
}

// → { ok, message } for the text of an AGENTS.shared.md.
export function check(text) {
  const parts = split(text);
  if (!parts) return { ok: false, message: `${FILE_NAME} has no "master-sha256" header line. Run ${SCRIPT} to copy the master again.` };
  if (bodyHash(parts.body) !== parts.recorded) {
    return {
      ok: false,
      message: parts.isMaster
        ? `${FILE_NAME} (the master) changed without a new hash. If the edit is meant, run ${SCRIPT} --stamp.`
        : `${FILE_NAME} was edited by hand. Undo the edit (or run ${SCRIPT} to copy the master again) and make the change in the master in ${MASTER_REPO}.`,
    };
  }
  return { ok: true, message: `${FILE_NAME} matches its recorded master hash ${parts.recorded.slice(0, 12)}` };
}

// Master text → the text of a copy. Refuses a master whose own hash is stale.
export function makeCopy(masterText) {
  const parts = split(masterText);
  if (!parts || !parts.isMaster) throw new Error(`that file is not the master ${FILE_NAME}`);
  const verdict = check(masterText);
  if (!verdict.ok) throw new Error(`the master is not stamped: ${verdict.message}`);
  return `${copyHeader(parts.recorded)}\n${parts.body}`;
}

// Master text after an edit → the same text with its hash recorded.
export function stamp(masterText) {
  const parts = split(masterText);
  if (!parts || !parts.isMaster) throw new Error(`--stamp works only on the master ${FILE_NAME}`);
  return `${masterHeader(bodyHash(parts.body))}\n${parts.body}`;
}

function readMaster(from) {
  if (from) {
    const p = resolve(from);
    const file = existsSync(p) && statSync(p).isDirectory() ? join(p, FILE_NAME) : p;
    return readFileSync(file, "utf8");
  }
  return execFileSync("gh", ["api", "-H", "Accept: application/vnd.github.raw", `repos/${MASTER_REPO}/contents/${FILE_NAME}?ref=main`], { encoding: "utf8" });
}

function main(args) {
  const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
  const target = join(root, FILE_NAME);
  if (args.includes("--check")) {
    const r = existsSync(target) ? check(readFileSync(target, "utf8")) : { ok: false, message: `${FILE_NAME} is missing. Run ${SCRIPT}.` };
    console.log(`${r.ok ? "ok" : "FAIL"}: ${r.message}`);
    return r.ok ? 0 : 1;
  }
  if (args.includes("--stamp")) {
    writeFileSync(target, stamp(readFileSync(target, "utf8")));
    console.log(`stamped ${FILE_NAME}: ${check(readFileSync(target, "utf8")).message}`);
    return 0;
  }
  const i = args.indexOf("--from");
  const from = i === -1 ? null : args[i + 1];
  if (existsSync(target) && split(readFileSync(target, "utf8"))?.isMaster) {
    console.error(`This repo holds the master ${FILE_NAME}; there is nothing to copy. Use --stamp after an edit.`);
    return 1;
  }
  const copy = makeCopy(readMaster(from));
  const before = existsSync(target) ? readFileSync(target, "utf8") : "";
  writeFileSync(target, copy);
  console.log(before === copy ? `${FILE_NAME} already matches the master.` : `${FILE_NAME} updated from the master. Commit it in its own PR.`);
  return 0;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    process.exit(main(process.argv.slice(2)));
  } catch (err) {
    console.error(`sync-shared-rules: ${err.message}`);
    process.exit(1);
  }
}
