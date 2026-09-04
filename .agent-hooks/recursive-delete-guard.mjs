#!/usr/bin/env node

const blockedPatterns = [
  [
    "rm recursive deletion",
    /\brm(?:\.exe)?\s+(?=[^\r\n;&|]*(?:--recursive\b|-[a-z]*r[a-z]*\b))/i,
  ],
  [
    "PowerShell recursive deletion",
    /\b(?:remove-item|del|erase|rmdir|rd|ri)\b[^\r\n;|]*\s-(?:recurse|r)\b/i,
  ],
  [
    "Windows recursive directory deletion",
    /\b(?:rmdir|rd)(?:\.exe)?\b[^\r\n&|]*\s\/s\b/i,
  ],
  [
    "recursive git removal",
    /\bgit\s+rm\b[^\r\n;&|]*(?:\s-r\b|\s--recursive\b)/i,
  ],
  [
    "git clean directory deletion",
    /\bgit\s+clean\b[^\r\n;&|]*(?:\s--directories\b|\s-d\b|-[a-z]*d[a-z]*\b)/i,
  ],
  ["git worktree deletion", /\bgit\s+worktree\s+remove\b/i],
  ["Python recursive deletion", /\bshutil\.rmtree\s*\(/i],
  ["rimraf recursive deletion", /\brimraf\b/i],
  [
    "Node.js recursive deletion",
    /\b(?:fs\.)?rm(?:sync)?\s*\([^)]*recursive\s*:\s*true/i,
  ],
];

export function blockedReason(command) {
  for (const [label, pattern] of blockedPatterns) {
    if (pattern.test(command)) {
      return `Blocked ${label}. Review and run the command manually if intentional.`;
    }
  }
  return null;
}

function commandFrom(payload) {
  const command = payload?.tool_input?.command;
  return typeof command === "string" ? command : "";
}

function responseFor(event, reason) {
  if (event === "BeforeTool") {
    return reason ? { decision: "deny", reason } : { decision: "allow" };
  }

  if (!reason) return {};
  return {
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: reason,
    },
  };
}

async function runHook() {
  let payload;
  try {
    const chunks = [];
    for await (const chunk of process.stdin) chunks.push(chunk);
    payload = JSON.parse(Buffer.concat(chunks).toString("utf8"));
  } catch {
    process.stdout.write("{}\n");
    return;
  }

  const event = typeof payload?.hook_event_name === "string"
    ? payload.hook_event_name
    : "PreToolUse";
  const response = responseFor(event, blockedReason(commandFrom(payload)));
  process.stdout.write(`${JSON.stringify(response)}\n`);
}

function selfTest() {
  const blocked = [
    "rm -rf build",
    "Remove-Item -LiteralPath build -Recurse -Force",
    "rmdir build -Recurse",
    "cmd /c rd /s /q build",
    "git clean -fd",
    "git clean --force --directories",
    "git rm -r generated",
    "git worktree remove ../tmp",
    "python -c \"import shutil; shutil.rmtree('build')\"",
    "npx rimraf build",
    "fs.rmSync(path, { recursive: true })",
    "echo $(rm -rf build)",
  ];
  const allowed = [
    "rm file.txt",
    "Remove-Item -LiteralPath file.txt",
    "rmdir empty-directory",
    "git clean -n",
    "git rm file.txt",
  ];

  const failures = blocked.filter((command) => !blockedReason(command));
  failures.push(...allowed.filter((command) => blockedReason(command)));
  const preToolDeny = responseFor("PreToolUse", blockedReason("rm -rf build"));
  const beforeToolDeny = responseFor("BeforeTool", blockedReason("rm -rf build"));
  const beforeToolAllow = responseFor("BeforeTool", blockedReason("rm file.txt"));
  if (preToolDeny?.hookSpecificOutput?.permissionDecision !== "deny") {
    failures.push("PreToolUse deny response");
  }
  if (beforeToolDeny?.decision !== "deny") failures.push("BeforeTool deny response");
  if (beforeToolAllow?.decision !== "allow") failures.push("BeforeTool allow response");
  if (failures.length > 0) {
    for (const command of failures) console.error(`FAIL: ${command}`);
    process.exitCode = 1;
    return;
  }
  console.log(
    `PASS: ${blocked.length + allowed.length} command cases and 3 hook response cases`,
  );
}

if (process.argv.includes("--self-test")) {
  selfTest();
} else {
  await runHook();
}
