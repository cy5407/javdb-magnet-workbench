#!/usr/bin/env python3
"""遞迴刪除與破壞性工作區操作的統一守衛（四家 runner 共用）。

本檔取代舊的 recursive-delete-guard.mjs。改用 Python 的理由：
Antigravity 端 ~/.gemini/config/hooks/pre_tool_guard.py 才是三家裡規則最完整、
且唯一 fail-closed 的實作，把它升格成正典比反過來把 .mjs 補齊安全。

三個設計約束，改動時不要破壞：

1. fail-closed。取不到指令字串就是判定不了，判定不了一律 deny。舊 .mjs 在
   解析失敗時輸出 {} 等於放行，形狀一變就靜默失效而且沒有任何訊號。
2. 多形狀 payload。同一支 hook 被三家以不同 JSON 形狀呼叫，只認一種等於
   對其餘兩家全盲——這正是 2026-09-03 Antigravity 靜默放行的成因。
3. 回應形狀依 runner 互斥分流。Claude Code / Codex 使用 hookSpecificOutput；
   Antigravity / Gemini CLI 使用 top-level decision。註冊檔以 --runner 明示身分。
"""

import json
import os
import re
import shlex
import sys
import threading

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")

STDIN_TIMEOUT_SECONDS = 5

# ── 規則 ──────────────────────────────────────────────────────────────────
#
# 兩組分開的理由：只有 FILESYSTEM_RECURSIVE 這組適用建置產物白名單。
# 破壞性 git 與鏡像清空的「目標」不是一個可解析的路徑，放行條件無從判定，
# 因此一律 deny。

FILESYSTEM_RECURSIVE = [
    # POSIX rm / trash：支援可選絕對路徑（如 /bin/rm）、-r、-R、--recursive 或複合旗標
    r'(?:^|[\s;&|("`\'$])(?:[\w./\\-]+[/\\])?(?:rm|trash)(?:\.exe)?\s+(?:-[a-zA-Z]*[rR][a-zA-Z]*|--recursive)(?:\s|$)',
    # PowerShell Remove-Item / rm / del / rd / ri / rmdir / erase 帶 -Recurse（含縮寫）
    r'(?:^|[\s;&|("`\'$])(?:Remove-Item|rm|del|rd|ri|rmdir|erase)\s+.*-(?:r|rec|recur|recurse)(?:\s|$)',
    # CMD rmdir / rd / del / erase 帶 /s
    r'(?:^|[\s;&|("`\'$])(?:[\w./\\-]+[/\\])?(?:rmdir|rd|del|erase)(?:\.exe)?\s+.*\/[sS](?:\s|$)',
]

# 上游 -Recurse 列舉再接刪除：Get-ChildItem -Recurse | Remove-Item。
# 目標藏在 pipeline 上游，抽不出單一路徑，所以不適用白名單。
PIPELINE_RECURSIVE = [
    r'-[rR](?:ecurse|ecurs|ecur|ecu|ec|e)?\b[^|]*\|\s*(?:Remove-Item|rm|del|ri|rmdir|rd)\b',
]

DESTRUCTIVE_OTHER = [
    # git 遞迴刪除
    r'(?:^|[\s;&|("`\'$])git\s+rm\s+.*-[a-zA-Z]*[rR]',
    # git clean 帶 -f / -d / --force / --directories（負向後行斷言避免誤殺 --dry-run）
    r'(?:^|[\s;&|("`\'$])git\s+clean\s+.*(?:(?<!-)-[a-zA-Z]*[fFdD][a-zA-Z]*\b|--force\b|--directories\b)',
    # git reset --hard
    r'(?:^|[\s;&|("`\'$])git\s+reset\s+.*--hard\b',
    # git restore . / *（單檔如 git restore file.txt 放行）
    r'(?:^|[\s;&|("`\'$])git\s+restore\s+(?:.*?\s)?(?:\.|\*)(?:\s|$)',
    # git checkout -f / git checkout -- .
    r'(?:^|[\s;&|("`\'$])git\s+checkout\s+.*(?:-[a-zA-Z]*[fF]\b|--\s+\.)',
    # find ... -delete / -exec rm
    r'(?:^|[\s;&|("`\'$])find\s+.*(?:-delete|-exec\s+rm)',
    # 程式庫單行遞迴刪除
    r'shutil\.rmtree',
    r'fs\.rm(?:Sync)?\(.*recursive\s*:\s*true',
    r'\[System\.IO\.Directory\]::Delete\(.*,\s*\$true\)',
    r'(?:^|[\s;&|("`\'$])(?:(?:npx|bunx)\s+)?rimraf\b',
    # 鏡像一個空來源等於清空目標
    r'(?:^|[\s;&|("`\'$])robocopy(?:\.exe)?\s+.*\/(?:MIR|PURGE)\b',
]

FS_REGEX = re.compile('|'.join(FILESYSTEM_RECURSIVE), re.IGNORECASE)
PIPELINE_REGEX = re.compile('|'.join(PIPELINE_RECURSIVE), re.IGNORECASE)
OTHER_REGEX = re.compile('|'.join(DESTRUCTIVE_OTHER), re.IGNORECASE)

# git worktree remove 刻意不列入：它是既有例外，見下方 EXEMPT_PATTERNS。
# git 自己會拒絕移除有未提交變更的工作樹，而且目標永遠是 git 自己管理的目錄。
EXEMPT_PATTERNS = [
    r'(?:^|[\s;&|])git\s+worktree\s+remove',
]
EXEMPT_REGEX = re.compile('|'.join(EXEMPT_PATTERNS), re.IGNORECASE)

# 允許遞迴刪除的目錄名（必須是解析後路徑的最後一段）
DISPOSABLE_DIR_NAMES = {
    "build", "target", "dist", "out",
    "node_modules", "__pycache__",
    ".venv", "venv",
    ".pytest_cache", ".ruff_cache", ".mypy_cache",
    "coverage", ".next", ".turbo",
    "tmp", ".tmp", "scratchpad",
}

# 這些旗標吃一個「值」，該值不是刪除目標，抽目標時要一起跳過。
FLAGS_TAKING_VALUE = {
    "-exclude", "-include", "-filter", "-encoding", "-erroraction",
    "--exclude", "--include",
}


def _temp_roots():
    roots = []
    for key in ("TEMP", "TMP", "TMPDIR"):
        value = os.environ.get(key)
        if value:
            try:
                roots.append(os.path.realpath(os.path.abspath(value)))
            except OSError:
                continue
    return roots


def _is_within(child, parent):
    """child 是否位於 parent 底下（不含 parent 本身）。"""
    try:
        return os.path.commonpath([child, parent]) == parent and child != parent
    except ValueError:
        # 不同磁碟機代號在 Windows 上會拋 ValueError，視為不在底下。
        return False


def _has_git_dir(path):
    return os.path.isdir(os.path.join(path, ".git")) or os.path.isfile(os.path.join(path, ".git"))


def extract_delete_targets(command_line):
    """從 shell 刪除指令抽出目標路徑 token。

    抽不出來、或抽出的東西不足以判定時回傳 None，呼叫端據此 deny。
    posix=False 是為了讓 Windows 路徑的反斜線不被當成跳脫字元。
    """
    try:
        tokens = shlex.split(command_line, posix=False)
    except ValueError:
        return None
    if not tokens:
        return None

    targets = []
    skip_next = False
    for token in tokens[1:]:
        if skip_next:
            skip_next = False
            continue
        stripped = token.strip('"\'')
        if not stripped:
            continue
        lowered = stripped.lower()
        if lowered in FLAGS_TAKING_VALUE:
            skip_next = True
            continue
        # 旗標：-rf、--recursive、/s、-LiteralPath …
        if stripped.startswith("-") or (len(stripped) <= 3 and stripped.startswith("/")):
            continue
        targets.append(stripped)
    return targets


def disposable_target_reason(command_line, cwd=None):
    """判斷遞迴刪除的目標是否落在可拋棄目錄白名單。

    回傳 None 表示放行；回傳字串表示拒絕的原因。
    保守到底：任何一個判定不了的環節都拒絕，不猜。
    """
    cwd = os.path.realpath(os.path.abspath(cwd or os.getcwd()))
    targets = extract_delete_targets(command_line)

    if targets is None:
        return "無法解析指令中的刪除目標（引號不成對？）。"
    if len(targets) == 0:
        return "指令中找不到明確的刪除目標。"
    if len(targets) > 1:
        return f"一次指定了多個刪除目標（{', '.join(targets)}），白名單只接受單一目標。"

    target = targets[0]

    if any(ch in target for ch in "*?["):
        return f"刪除目標含萬用字元（{target}），無法預先確定會刪到什麼。"
    if ".." in target.replace("\\", "/").split("/"):
        return f"刪除目標含上層參照 ..（{target}），解析後可能逃出工作目錄。"

    resolved = os.path.realpath(os.path.abspath(os.path.join(cwd, target)))

    if resolved == cwd:
        return "刪除目標就是目前工作目錄本身。"
    if _has_git_dir(resolved):
        return f"刪除目標是一個 repo 根目錄（{resolved}）。"

    in_cwd = _is_within(resolved, cwd)
    in_temp = any(_is_within(resolved, root) for root in _temp_roots())
    if not in_cwd and not in_temp:
        return f"刪除目標不在目前工作目錄或系統暫存區底下（{resolved}）。"

    basename = os.path.basename(resolved)
    if basename not in DISPOSABLE_DIR_NAMES:
        return (
            f"目錄名 {basename} 不在可拋棄白名單內。"
            f"白名單：{', '.join(sorted(DISPOSABLE_DIR_NAMES))}"
        )
    return None


def check_command(command_line, cwd=None):
    """回傳 (allowed, reason)。allowed 為 True 時 reason 為空字串。"""
    if not command_line:
        return False, "指令字串為空，無法判定是否為遞迴刪除。"

    # 例外只豁免「它自己那一段」，不豁免整條命令列。
    #
    # 原本是 `if EXEMPT_REGEX.search(command_line): return True`——只要命令文字
    # 裡任何地方出現「git worktree remove」，整段複合指令就提前獲准。實測
    # （2026-09-23，Codex 在覆核中發現、本機逐條重現）：
    #
    #   git reset --hard; git worktree remove unused        -> allowed
    #   echo git worktree remove; git reset --hard          -> allowed
    #   git reset --hard # git worktree remove              -> allowed
    #   rm -rf /etc && git worktree remove unused           -> allowed
    #
    # 最後一條是完全繞過：只要在後面接一句例外，遞迴刪除任何路徑都會放行。
    #
    # 改成先把例外段落從文字裡拿掉，再拿剩下的去比對。用空白取代而不是刪空，
    # 是為了不讓兩側的 token 黏在一起——例外的樣式本身含一個前導邊界字元
    # （`[\s;&|]`），整段拿掉會把那個分隔符一併帶走。
    #
    # 這不是 shell 剖析，是保守的減法：只會移除文字，不會生出新的放行條件。
    remainder = EXEMPT_REGEX.sub(" ", command_line)

    if OTHER_REGEX.search(remainder) or PIPELINE_REGEX.search(remainder):
        return False, _blocked_reason(command_line, "")

    if FS_REGEX.search(remainder):
        detail = disposable_target_reason(remainder, cwd)
        if detail is None:
            return True, ""
        return False, _blocked_reason(command_line, detail)

    return True, ""


def _blocked_reason(command_line, detail):
    lines = [
        "[BLOCKED] 檢測到遞迴刪除或破壞性工作區指令。",
        f"指令內容: {command_line}",
    ]
    if detail:
        lines.append(f"未通過白名單的原因: {detail}")
    lines.extend([
        "安全規範：",
        "1. 檔案系統：禁止遞迴刪除，僅允許單檔逐一刪除。目標明確落在工作目錄底下的",
        f"   建置產物或暫存目錄（{', '.join(sorted(DISPOSABLE_DIR_NAMES))}）才放行。",
        "2. 版本控制：禁止破壞性抹除工作區（git reset --hard、git clean -f/-fd、",
        "   git restore . 等）。要放棄修改請先 git stash push -u 保全未提交資產。",
        "3. git worktree remove 不在此限，可直接執行。",
        "若這次確實需要，請停下來說明，由使用者自己手動執行。",
    ])
    return "\n".join(lines)


CLAUDE_SHAPE_RUNNERS = {"claude", "codex"}
DECISION_SHAPE_RUNNERS = {"antigravity", "gemini"}


def infer_runner(payload):
    """舊註冊未傳 --runner 時的相容 fallback；新註冊不得依賴此推測。"""
    if isinstance(payload, dict) and payload.get("hook_event_name") == "BeforeTool":
        return "gemini"
    if isinstance(payload, dict) and (
        "toolName" in payload or "toolCall" in payload or "args" in payload
    ):
        return "antigravity"
    return "claude"


def _response(decision, reason, runner=None, payload=None):
    runner = runner or infer_runner(payload)
    if runner in DECISION_SHAPE_RUNNERS:
        res = {"decision": decision}
        if reason:
            res["reason"] = reason
        return res
    if decision == "allow":
        return {}
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason or "",
        },
    }


def emit(decision, reason="", runner=None, payload=None):
    if decision == "deny" and reason:
        print(reason, file=sys.stderr)
    print(json.dumps(_response(decision, reason, runner, payload), ensure_ascii=False))
    sys.stdout.flush()


def command_from_payload(payload):
    """四種已知形狀依序嘗試；都取不到就回傳空字串（呼叫端 deny）。"""
    if not isinstance(payload, dict):
        return ""
    tool_call = payload.get("toolCall")
    if isinstance(tool_call, dict):
        args = tool_call.get("args")
        if isinstance(args, dict):
            for key in ("CommandLine", "command"):
                value = args.get(key)
                if isinstance(value, str) and value:
                    return value
    args = payload.get("args")
    if isinstance(args, dict):
        for key in ("CommandLine", "command"):
            value = args.get(key)
            if isinstance(value, str) and value:
                return value
    tool_input = payload.get("tool_input")
    if isinstance(tool_input, dict):
        value = tool_input.get("command")
        if isinstance(value, str) and value:
            return value
    return ""


def _watchdog(runner=None):
    """stdin 永遠不關的情況下仍要給出判定。

    runner 端的 timeout 設定無法從外部確認，不能當作唯一保險。逾時走 deny
    是因為「等不到輸入」與「解析不出輸入」同樣屬於判定不了。
    """
    emit("deny", f"hook 等待 stdin 超過 {STDIN_TIMEOUT_SECONDS} 秒仍未取得完整輸入，無法判定。", runner)
    os._exit(0)


def run_hook(runner=None):
    timer = threading.Timer(STDIN_TIMEOUT_SECONDS, _watchdog, args=(runner,))
    timer.daemon = True
    timer.start()
    try:
        try:
            raw = sys.stdin.read().strip()
        except Exception as exc:
            emit("deny", f"無法讀取 hook stdin：{exc!r}", runner)
            return
        if not raw:
            emit("deny", "hook 收到空的 stdin，無法取得指令內容。", runner)
            return
        try:
            payload = json.loads(raw)
        except Exception as exc:
            emit("deny", f"無法解析 hook payload：{exc!r}", runner)
            return

        command_line = command_from_payload(payload)
        if not command_line:
            emit("deny", "hook payload 中找不到指令字串（已嘗試 toolCall.args.CommandLine／"
                         "toolCall.args.command／args.CommandLine／tool_input.command）。",
                 runner=runner, payload=payload)
            return

        allowed, reason = check_command(command_line)
        emit("allow" if allowed else "deny", reason, runner=runner, payload=payload)
    finally:
        timer.cancel()


# ── 自我測試 ─────────────────────────────────────────────────────────────

def run_tests():
    import tempfile

    command_cases = [
        # 單檔刪除與合法操作放行
        ("rm file.txt", True),
        ("Remove-Item C:\\temp\\log.txt", True),
        ("del app.log", True),
        ("ls -la", True),
        ("Get-ChildItem *.tmp | Remove-Item", True),
        ("git worktree list", True),
        ("robocopy C:\\a C:\\b /E", True),
        ("git reset HEAD file.txt", True),
        ("git restore file.txt", True),
        ("git checkout -b new-branch", True),
        ("git checkout main", True),
        ("git stash push -u", True),
        ("git status", True),
        ("git rm file.txt", True),
        ("git clean -n", True),
        # 例外：git worktree remove 放行
        ("git worktree remove ../wt-foo", True),
        ("git worktree remove --force ../wt-foo", True),
        # 破壞性 git 一律擋
        ("git clean -f", False),
        ("git clean -fd", False),
        ("git clean --force", False),
        ("git reset --hard", False),
        ("git reset --hard HEAD~1", False),
        ("git restore .", False),
        ("git restore *", False),
        ("git checkout -f", False),
        ("git checkout -- .", False),
        ("git rm -r generated", False),
        # 程式庫單行與鏡像
        ("python -c \"import shutil; shutil.rmtree('dist')\"", False),
        ("npx rimraf build", False),
        ("fs.rmSync(path, { recursive: true })", False),
        ("robocopy C:\\empty C:\\target /MIR", False),
        ("find . -delete", False),
        ("find . -exec rm {} \\;", False),
        # pipeline 遞迴：目標抽不出來，不適用白名單
        ("Get-ChildItem -Recurse *.tmp | Remove-Item", False),
        ("gci -Recurse | Remove-Item -Force", False),
        # 遞迴刪除且目標不在白名單
        ("rm -rf src", False),
        ("rm -rf /", False),
        ("rm -rf ~", False),
        ("Remove-Item src -Recurse", False),
        ("rmdir /s /q src", False),
        # 白名單繞過手法一律擋
        ("rm -rf build/../..", False),
        ("rm -rf ../build", False),
        ("rm -rf build src", False),
        ("rm -rf *", False),
        ("rm -rf build*", False),
        ("rm -rf .", False),
    ]

    failures = []
    for command, expected in command_cases:
        actual, _ = check_command(command)
        if actual != expected:
            failures.append(f"指令判定: {command} (預期放行={expected}, 實際={actual})")

    # 白名單放行：在一個真實的暫存工作目錄底下建出目標，避免依賴 CWD 現況。
    with tempfile.TemporaryDirectory() as workdir:
        real_workdir = os.path.realpath(workdir)
        for name in ("build", "node_modules", "__pycache__"):
            os.makedirs(os.path.join(real_workdir, name), exist_ok=True)
        os.makedirs(os.path.join(real_workdir, "src"), exist_ok=True)
        os.makedirs(os.path.join(real_workdir, "nested", "target"), exist_ok=True)

        allow_in_cwd = [
            "rm -rf build",
            "rm -rf ./build",
            "rm -rf node_modules",
            "rm -rf __pycache__",
            "Remove-Item build -Recurse -Force",
            "rm -rf nested/target",
        ]
        deny_in_cwd = [
            "rm -rf src",
            "rm -rf nested",
        ]
        for command in allow_in_cwd:
            allowed, reason = check_command(command, cwd=real_workdir)
            if not allowed:
                failures.append(f"白名單應放行: {command} -> {reason.splitlines()[0]}")
        for command in deny_in_cwd:
            allowed, _ = check_command(command, cwd=real_workdir)
            if allowed:
                failures.append(f"白名單應拒絕: {command}")

        # repo 根即使名為 build 也不放行
        repo_build = os.path.join(real_workdir, "buildrepo")
        os.makedirs(os.path.join(repo_build, ".git"), exist_ok=True)
        allowed, _ = check_command("rm -rf buildrepo", cwd=real_workdir)
        if allowed:
            failures.append("白名單應拒絕: repo 根目錄")

    payload_cases = [
        ("Claude tool_input.command",
         {"hook_event_name": "PreToolUse", "tool_name": "Bash",
          "tool_input": {"command": "rm -rf src"}}, "rm -rf src"),
        ("Antigravity toolCall.args.CommandLine",
         {"toolCall": {"args": {"CommandLine": "rm -rf src"}}}, "rm -rf src"),
        ("Antigravity args.CommandLine",
         {"args": {"CommandLine": "rm -rf src"}}, "rm -rf src"),
        ("toolCall.args.command",
         {"toolCall": {"args": {"command": "rm -rf src"}}}, "rm -rf src"),
        ("未知形狀", {"command": "rm -rf src"}, ""),
        ("非物件", ["rm -rf src"], ""),
    ]
    for label, payload, expected in payload_cases:
        actual = command_from_payload(payload)
        if actual != expected:
            failures.append(f"payload 形狀: {label} (預期={expected!r}, 實際={actual!r})")

    shape_cases = [
        ("claude", "deny", ["hookSpecificOutput"]),
        ("codex", "deny", ["hookSpecificOutput"]),
        ("antigravity", "deny", ["decision", "reason"]),
        ("gemini", "deny", ["decision", "reason"]),
        ("claude", "allow", []),
        ("codex", "allow", []),
        ("antigravity", "allow", ["decision"]),
        ("gemini", "allow", ["decision"]),
    ]
    for runner, decision, expected_keys in shape_cases:
        keys = sorted(_response(decision, "reason" if decision == "deny" else "", runner).keys())
        if keys != sorted(expected_keys):
            failures.append(f"回應形狀: runner={runner} {decision} -> {keys}")

    fallback_cases = [
        ({"hook_event_name": "PreToolUse", "tool_name": "Bash"}, "claude"),
        ({"hook_event_name": "BeforeTool", "tool_name": "run_shell_command"}, "gemini"),
        ({"toolName": "run_command"}, "antigravity"),
    ]
    for payload, expected in fallback_cases:
        actual = infer_runner(payload)
        if actual != expected:
            failures.append(f"runner fallback: expected={expected} actual={actual}")

    if failures:
        for failure in failures:
            print(f"[FAIL] {failure}", file=sys.stderr)
        return False

    total = len(command_cases) + 9 + len(payload_cases) + len(shape_cases) + len(fallback_cases)
    print(f"[SUCCESS] recursive_delete_guard.py — {total} 項全部通過"
          f"（{len(command_cases)} 指令、9 白名單路徑、{len(payload_cases)} payload 形狀、"
          f"{len(shape_cases)} 回應形狀、{len(fallback_cases)} fallback）")
    return True


def main():
    args = sys.argv[1:]
    if any(arg in ("--test", "-t", "test") for arg in args):
        sys.exit(0 if run_tests() else 1)

    runner = None
    if "--runner" in args:
        idx = args.index("--runner")
        if idx + 1 < len(args):
            candidate = args[idx + 1].lower()
            if candidate in CLAUDE_SHAPE_RUNNERS | DECISION_SHAPE_RUNNERS:
                runner = candidate
            del args[idx:idx + 2]

    if args:
        arg = args[0]
        allowed, reason = check_command(arg)
        if allowed:
            print(f"[ALLOWED] {arg}")
            sys.exit(0)
        print(reason, file=sys.stderr)
        sys.exit(1)

    if sys.stdin.isatty():
        run_tests()
        return

    run_hook(runner)


if __name__ == "__main__":
    main()
