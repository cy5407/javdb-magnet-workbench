#!/usr/bin/env python3
"""窮舉測試矩陣 (Exhaustive Guard Test Matrix)

檢驗 recursive_delete_guard.py 的所有邊界值、語法變體、攻擊向量、白名單路徑與多 Runner 相容性。
包含 176 項自動化單元與黑箱端對端測試。
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# 動態匯入同目錄下的守衛
GUARD_PATH = Path(__file__).resolve().parent / "recursive_delete_guard.py"
if not GUARD_PATH.is_file():
    print(f"FATAL: Guard not found at {GUARD_PATH}", file=sys.stderr)
    sys.exit(1)

spec = importlib.util.spec_from_file_location("guard", str(GUARD_PATH))
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def run_exhaustive_tests():
    total_passed = 0
    total_failed = 0
    failures = []

    def check(category, case_id, condition, detail=""):
        nonlocal total_passed, total_failed
        if condition:
            total_passed += 1
        else:
            total_failed += 1
            msg = f"[{category}] FAIL ({case_id}): {detail}"
            print(msg, file=sys.stderr)
            failures.append(msg)

    print("================================================================================")
    print(" 窮舉測試矩陣 (Exhaustive Test Matrix) 啟動")
    print("================================================================================")

    # ──────────────────────────────────────────────────────────────────────────
    # 矩陣 1: POSIX / Unix rm 指令語法變體
    # ──────────────────────────────────────────────────────────────────────────
    posix_cases = [
        # (指令, 預期允許)
        ("rm -r somedir", False),
        ("rm -rf somedir", False),
        ("rm -fr somedir", False),
        ("rm -rfi somedir", False),
        ("rm -rfv somedir", False),
        ("rm -R somedir", False),
        ("rm -Rf somedir", False),
        ("rm --recursive somedir", False),
        ("rm.exe -rf somedir", False),
        ("/bin/rm -rf somedir", False),
        ("trash -r somedir", False),
        ("trash --recursive somedir", False),
        # 合法單檔 / 旗標放行
        ("rm file.txt", True),
        ("rm -f file.txt", True),
        ("rm -v file.txt", True),
        ("rm --force file.txt", True),
        ("rm a.txt b.txt c.txt", True),
        ("rm -i important.txt", True),
    ]
    for cmd, expected in posix_cases:
        allowed, reason = guard.check_command(cmd)
        check("1. POSIX rm", cmd, allowed == expected, f"預期 {expected}，實際 {allowed} ({reason})")

    # ──────────────────────────────────────────────────────────────────────────
    # 矩陣 2: PowerShell 指令與別名變體
    # ──────────────────────────────────────────────────────────────────────────
    pwsh_cases = [
        ("Remove-Item -Recurse somedir", False),
        ("Remove-Item -recurse somedir", False),
        ("Remove-Item -r somedir", False),
        ("Remove-Item -rec somedir", False),
        ("Remove-Item -recur somedir", False),
        ("Remove-Item -Force -Recurse somedir", False),
        ("Remove-Item somedir -Recurse -Force", False),
        ("Remove-Item -LiteralPath somedir -Recurse", False),
        ("rm -r somedir", False),
        ("rm -recurse somedir", False),
        ("del -r somedir", False),
        ("del -recurse somedir", False),
        ("erase -r somedir", False),
        ("rmdir -r somedir", False),
        ("rd -r somedir", False),
        ("ri -r somedir", False),
        ("ri -recurse somedir", False),
        # 管道列舉遞迴刪除
        ("Get-ChildItem -Recurse | Remove-Item", False),
        ("Get-ChildItem -r | Remove-Item", False),
        ("gci -Recurse | ri", False),
        ("gci -r | ri", False),
        ("ls -Recurse | rm", False),
        ("dir -r | del", False),
        # 合法單檔 / 單層列舉放行
        ("Remove-Item file.txt", True),
        ("Remove-Item -Force file.txt", True),
        ("Remove-Item -LiteralPath file.txt", True),
        ("rm file.txt", True),
        ("del file.txt", True),
        ("erase file.txt", True),
        ("rmdir emptyDir", True),
        ("rd emptyDir", True),
        ("Get-ChildItem *.tmp | Remove-Item", True),
        ("ls *.log | Remove-Item", True),
    ]
    for cmd, expected in pwsh_cases:
        allowed, reason = guard.check_command(cmd)
        check("2. PowerShell", cmd, allowed == expected, f"預期 {expected}，實際 {allowed} ({reason})")

    # ──────────────────────────────────────────────────────────────────────────
    # 矩陣 3: Windows CMD 指令變體
    # ──────────────────────────────────────────────────────────────────────────
    cmd_cases = [
        ("rmdir /s somedir", False),
        ("rmdir /S somedir", False),
        ("rmdir /S /Q somedir", False),
        ("rmdir.exe /s somedir", False),
        ("rd /s somedir", False),
        ("rd /S /Q somedir", False),
        ("rd.exe /s somedir", False),
        ("del /s file.txt", False),
        ("del.exe /S file.txt", False),
        ("erase /s file.txt", False),
        ("cmd /c rd /s /q somedir", False),
        ("cmd.exe /c rmdir /s /q somedir", False),
        # 合法單檔 / 空目錄放行
        ("rmdir emptyDir", True),
        ("rd emptyDir", True),
        ("del file.txt", True),
        ("del /f file.txt", True),
        ("del /q file.txt", True),
        ("erase file.txt", True),
    ]
    for cmd, expected in cmd_cases:
        allowed, reason = guard.check_command(cmd)
        check("3. CMD", cmd, allowed == expected, f"預期 {expected}，實際 {allowed} ({reason})")

    # ──────────────────────────────────────────────────────────────────────────
    # 矩陣 4: 破壞性 Git 操作與唯讀放行
    # ──────────────────────────────────────────────────────────────────────────
    git_cases = [
        ("git rm -r somedir", False),
        ("git rm -rf somedir", False),
        ("git rm --recursive somedir", False),
        ("git clean -f", False),
        ("git clean -fd", False),
        ("git clean -fx", False),
        ("git clean -f -d", False),
        ("git clean --force", False),
        ("git clean --force -d", False),
        ("git reset --hard", False),
        ("git reset --hard HEAD~1", False),
        ("git reset --hard origin/main", False),
        ("git restore .", False),
        ("git restore *", False),
        ("git checkout -f", False),
        ("git checkout -- .", False),
        # 特例放行：git worktree remove
        ("git worktree remove path", True),
        ("git worktree remove --force path", True),
        ("git worktree remove -f ../wt-branch", True),
        # 唯讀 / 安全 Git 放行
        ("git status", True),
        ("git diff", True),
        ("git diff HEAD~1", True),
        ("git log -n 10", True),
        ("git show HEAD", True),
        ("git clean -n", True),
        ("git clean --dry-run", True),
        ("git rm file.txt", True),
        ("git rm -f file.txt", True),
        ("git restore file.txt", True),
        ("git checkout main", True),
        ("git checkout -b new-branch", True),
        ("git branch -a", True),
    ]
    for cmd, expected in git_cases:
        allowed, reason = guard.check_command(cmd)
        check("4. Git", cmd, allowed == expected, f"預期 {expected}，實際 {allowed} ({reason})")

    # ──────────────────────────────────────────────────────────────────────────
    # 矩陣 5: 系統呼叫、程式庫與外部清理工具
    # ──────────────────────────────────────────────────────────────────────────
    system_cases = [
        ("python -c \"import shutil; shutil.rmtree('dir')\"", False),
        ("python -c \"shutil.rmtree('dir')\"", False),
        ("python3 -c \"shutil.rmtree('build')\"", False),
        ("fs.rmSync(p, { recursive: true })", False),
        ("fs.rm(p, { recursive: true }, cb)", False),
        ("[System.IO.Directory]::Delete($p, $true)", False),
        ("npx rimraf dir", False),
        ("rimraf dir", False),
        ("find . -name '*.log' -delete", False),
        ("find . -exec rm -rf {} +", False),
        ("robocopy src dst /MIR", False),
        ("robocopy src dst /PURGE", False),
        ("robocopy.exe src dst /mir", False),
    ]
    for cmd, expected in system_cases:
        allowed, reason = guard.check_command(cmd)
        check("5. System/Tools", cmd, allowed == expected, f"預期 {expected}，實際 {allowed} ({reason})")

    # ──────────────────────────────────────────────────────────────────────────
    # 矩陣 5.5: 複合指令、子命令、引號包裹與大小寫混用變體
    # ──────────────────────────────────────────────────────────────────────────
    compound_cases = [
        ("echo hello && rm -rf src", False),
        ("git status ; Remove-Item -Recurse dir", False),
        ("echo $(rm -rf src)", False),
        ("powershell -c \"rm -r src\"", False),
        ("pwsh -Command \"Remove-Item -Recurse src\"", False),
        ("  RM   -RF   src  ", False),
        ("Git Clean -Fd", False),
        ("REMOVE-ITEM -RECURSE src", False),
        ("rMdIr /S /q dir", False),
        ("rm -rf \"src\"", False),
        ("rm -rf 'src'", False),
        ("Remove-Item -Recurse -LiteralPath \"src\"", False),
        ("Remove-Item -Recurse -LiteralPath 'src'", False),
    ]
    for cmd, expected in compound_cases:
        allowed, reason = guard.check_command(cmd)
        check("5.5 Compound/Quotes/Case", cmd, allowed == expected, f"預期 {expected}，實際 {allowed} ({reason})")

    # ──────────────────────────────────────────────────────────────────────────
    # 矩陣 6: 白名單目錄放行 vs 路徑遍歷跳脫防禦
    # ──────────────────────────────────────────────────────────────────────────
    with tempfile.TemporaryDirectory() as test_cwd:
        test_cwd_p = Path(test_cwd)
        # 建立白名單目錄
        for d in guard.DISPOSABLE_DIR_NAMES:
            (test_cwd_p / d).mkdir(parents=True, exist_ok=True)

        # 建立非白名單目錄
        (test_cwd_p / "src").mkdir(parents=True, exist_ok=True)
        (test_cwd_p / "internal").mkdir(parents=True, exist_ok=True)

        # 建立帶有 .git 的 repo 目錄
        git_repo_p = test_cwd_p / "sub_repo"
        git_repo_p.mkdir(parents=True, exist_ok=True)
        (git_repo_p / ".git").mkdir(parents=True, exist_ok=True)

        # 6.1 白名單目錄精確放行
        for d in guard.DISPOSABLE_DIR_NAMES:
            cmd = f"rm -rf {d}"
            allowed, reason = guard.check_command(cmd, cwd=test_cwd)
            check("6.1 Whitelist-Allow", cmd, allowed is True, f"白名單 {d} 應放行，實際: {allowed} ({reason})")

        # 6.2 路徑遍歷與非法目標攔截 (Path Traversal & Invalid Targets)
        traversal_cases = [
            ("rm -rf build/../..", False, "路徑含 .."),
            ("rm -rf ./build/../../src", False, "路徑含 .."),
            ("rm -rf ../build", False, "目標超出 CWD"),
            ("rm -rf *build*", False, "包含萬用字元 *"),
            ("rm -rf build?", False, "包含萬用字元 ?"),
            ("rm -rf build src", False, "多目標參數"),
            ("rm -rf .", False, "目前工作目錄本身"),
            ("rm -rf /", False, "系統根目錄"),
            ("rm -rf C:\\", False, "磁碟機根目錄"),
            ("rm -rf src", False, "非白名單目錄"),
            ("rm -rf internal", False, "非白名單目錄"),
            ("rm -rf sub_repo", False, "目標包含 .git (Repo 根)"),
        ]
        for cmd, expected, desc in traversal_cases:
            allowed, reason = guard.check_command(cmd, cwd=test_cwd)
            check("6.2 Path-Security", f"{cmd} ({desc})", allowed is False, f"應攔截，實際: {allowed} ({reason})")

    # ──────────────────────────────────────────────────────────────────────────
    # 矩陣 7: 多 Runner Payload 形狀解析與 Protojson 嚴格相容性
    # ──────────────────────────────────────────────────────────────────────────
    # 7.1 Antigravity Payload (嚴禁包含 hookSpecificOutput)
    agy_payload_1 = {"toolName": "run_command", "toolCall": {"args": {"CommandLine": "git status"}}}
    agy_payload_2 = {"toolName": "run_command", "args": {"CommandLine": "git status"}}
    agy_payload_3 = {"toolCall": {"args": {"command": "git status"}}}
    agy_payload_deny = {"toolName": "run_command", "args": {"CommandLine": "rm -rf src"}}

    # 這四項走 payload 推測（infer_runner），驗的是舊註冊未傳 --runner 時的相容路徑。
    # 明示 --runner 的主路徑另見 7.4。第三個位置參數是 runner 而非 payload，必須用
    # 關鍵字傳遞——2026-09-05 這裡曾因位置參數錯位讓整份套件以 TypeError 中止。
    resp_1 = guard._response("allow", "", payload=agy_payload_1)
    check("7.1 Antigravity", "toolCall.args.CommandLine allow",
          resp_1.get("decision") == "allow" and "hookSpecificOutput" not in resp_1,
          f"Antigravity 嚴禁包含 hookSpecificOutput: {resp_1}")

    resp_2 = guard._response("allow", "", payload=agy_payload_2)
    check("7.1 Antigravity", "args.CommandLine allow",
          resp_2.get("decision") == "allow" and "hookSpecificOutput" not in resp_2,
          f"Antigravity 嚴禁包含 hookSpecificOutput: {resp_2}")

    resp_3 = guard._response("allow", "", payload=agy_payload_3)
    check("7.1 Antigravity", "toolCall.args.command allow",
          resp_3.get("decision") == "allow" and "hookSpecificOutput" not in resp_3,
          f"Antigravity 嚴禁包含 hookSpecificOutput: {resp_3}")

    resp_deny = guard._response("deny", "blocked reason", payload=agy_payload_deny)
    check("7.1 Antigravity", "args.CommandLine deny",
          resp_deny.get("decision") == "deny" and resp_deny.get("reason") == "blocked reason" and "hookSpecificOutput" not in resp_deny,
          f"Antigravity deny 形狀錯誤: {resp_deny}")

    # 7.2 Claude Code / Codex Payload (必須包含 hookSpecificOutput)
    claude_payload_allow = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "git status"}}
    claude_payload_deny = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "rm -rf src"}}
    codex_payload = {"tool_name": "Bash", "tool_input": {"command": "rm -rf src"}}

    # Claude Code / Codex 的契約是「互斥」而非「合併」：allow 回空物件（沉默放行），
    # deny 只回 hookSpecificOutput 且不得夾帶 top-level decision。原本這三項斷言
    # 要求同時存在 decision 與 hookSpecificOutput，那是已被 REFUTED 的合併形狀假說
    # （見 [[hook_response_shape_runner_exclusivity]]），照舊斷言會把正確實作判成失敗。
    claude_res_allow = guard._response("allow", "", payload=claude_payload_allow)
    check("7.2 Claude/Codex", "Claude allow 為沉默放行",
          claude_res_allow == {},
          f"Claude allow 應為空物件，實際: {claude_res_allow}")

    claude_res_deny = guard._response("deny", "blocked reason", payload=claude_payload_deny)
    check("7.2 Claude/Codex", "Claude deny",
          "decision" not in claude_res_deny and
          claude_res_deny.get("hookSpecificOutput", {}).get("permissionDecision") == "deny" and
          claude_res_deny.get("hookSpecificOutput", {}).get("permissionDecisionReason") == "blocked reason",
          f"Claude deny 形狀錯誤: {claude_res_deny}")

    codex_res = guard._response("deny", "blocked reason", payload=codex_payload)
    check("7.2 Claude/Codex", "Codex deny",
          "decision" not in codex_res and
          codex_res.get("hookSpecificOutput", {}).get("permissionDecision") == "deny",
          f"Codex deny 形狀錯誤: {codex_res}")

    # 7.4 明示 --runner 的主路徑：四家形狀必須互斥，任一家夾帶另一家的欄位都是缺陷。
    for runner in ("claude", "codex"):
        allow_res = guard._response("allow", "", runner=runner)
        deny_res = guard._response("deny", "blocked reason", runner=runner)
        check("7.4 Runner 互斥", f"{runner} allow 為空物件",
              allow_res == {}, f"實際: {allow_res}")
        check("7.4 Runner 互斥", f"{runner} deny 只有 hookSpecificOutput",
              set(deny_res.keys()) == {"hookSpecificOutput"}, f"實際: {sorted(deny_res.keys())}")

    for runner in ("antigravity", "gemini"):
        allow_res = guard._response("allow", "", runner=runner)
        deny_res = guard._response("deny", "blocked reason", runner=runner)
        check("7.4 Runner 互斥", f"{runner} allow 只有 decision",
              set(allow_res.keys()) == {"decision"} and allow_res["decision"] == "allow",
              f"實際: {allow_res}")
        check("7.4 Runner 互斥", f"{runner} deny 只有 decision+reason",
              set(deny_res.keys()) == {"decision", "reason"} and deny_res["decision"] == "deny",
              f"實際: {sorted(deny_res.keys())}")

    # 7.3 Fail-Closed / 畸形 Payload 測試
    malformed_cases = [
        ("未知鍵值 dict", {"foo": "bar"}),
        ("空 dict", {}),
        ("列表 list", ["rm -rf src"]),
        ("純字串", "not a json"),
        ("None", None),
    ]
    for label, bad_input in malformed_cases:
        cmd_extracted = guard.command_from_payload(bad_input)
        check("7.3 Fail-Closed", f"提取指令為空 ({label})", cmd_extracted == "", f"預期空字串，實際: {cmd_extracted!r}")

    # ──────────────────────────────────────────────────────────────────────────
    # 矩陣 8: 子程序黑箱實測 (Process Stdin/Stdout/Watchdog Timeout)
    # ──────────────────────────────────────────────────────────────────────────
    # 8.1 透過真實子程序測試 Antigravity Allow
    proc_agy_allow = subprocess.run(
        [sys.executable, "-X", "utf8", str(GUARD_PATH)],
        input=json.dumps(agy_payload_1),
        text=True,
        capture_output=True,
    )
    check("8.1 Subprocess", "Antigravity Allow Exit Code 0", proc_agy_allow.returncode == 0)
    parsed_out = json.loads(proc_agy_allow.stdout.strip())
    check("8.1 Subprocess", "Antigravity Output Clean (No hookSpecificOutput)",
          parsed_out == {"decision": "allow"}, f"實際輸出: {parsed_out}")

    # 8.2 透過真實子程序測試 Claude Deny
    proc_claude_deny = subprocess.run(
        [sys.executable, "-X", "utf8", str(GUARD_PATH)],
        input=json.dumps(claude_payload_deny),
        text=True,
        capture_output=True,
    )
    check("8.2 Subprocess", "Claude Deny Exit Code 0", proc_claude_deny.returncode == 0)
    parsed_claude = json.loads(proc_claude_deny.stdout.strip())
    check("8.2 Subprocess", "Claude Deny Contains hookSpecificOutput",
          "decision" not in parsed_claude and
          parsed_claude.get("hookSpecificOutput", {}).get("permissionDecision") == "deny",
          f"實際輸出: {parsed_claude}")

    # 8.3 Watchdog 逾時機制測試 (開著 stdin 不送資料，驗證 5 秒 fail-closed)
    print("正在執行 Watchdog 5 秒逾時測試（預計耗時 ~5.1 秒）...")
    start_time = time.time()
    proc_watchdog = subprocess.Popen(
        [sys.executable, "-X", "utf8", str(GUARD_PATH)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    # 關鍵：不主動關閉 stdin，等待守衛的 watchdog timer 逾時主動 os._exit(0)
    try:
        proc_watchdog.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc_watchdog.kill()
        check("8.3 Watchdog", "Watchdog 超過 10 秒未退出", False)

    elapsed = time.time() - start_time
    stdout_data = proc_watchdog.stdout.read()

    check("8.3 Watchdog", "逾時時間落在 4.8 ~ 6.5 秒間", 4.8 <= elapsed <= 6.5, f"耗時: {elapsed:.2f}s")
    check("8.3 Watchdog", "逾時退出碼為 0 (不使 runner 崩潰)", proc_watchdog.returncode == 0)
    parsed_watchdog = json.loads(stdout_data.strip()) if stdout_data.strip() else {}
    # 這個子程序沒傳 --runner，逾時發生在讀到任何 payload 之前，因此 runner 仍是 None
    # 而落到 claude 形狀（hookSpecificOutput）。判定方向才是這裡要驗的東西，形狀只要
    # 是四家其中一種合法形狀即可，所以兩種都接受。
    watchdog_hso = parsed_watchdog.get("hookSpecificOutput", {})
    watchdog_decision = parsed_watchdog.get("decision") or watchdog_hso.get("permissionDecision")
    watchdog_reason = parsed_watchdog.get("reason") or watchdog_hso.get("permissionDecisionReason", "")
    check("8.3 Watchdog", "逾時判定為 deny", watchdog_decision == "deny", f"輸出: {parsed_watchdog}")
    check("8.3 Watchdog", "逾時訊息明確載明等待 stdin 逾時", "stdin 超過" in watchdog_reason,
          f"實際訊息: {watchdog_reason[:60]!r}")

    print("================================================================================")
    print(f" 測試結果: 總共 {total_passed + total_failed} 項測試，{total_passed} 通過，{total_failed} 失敗")
    print("================================================================================")

    if failures:
        print(f"\n失敗清單 ({len(failures)} 項):", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return False
    return True


if __name__ == "__main__":
    success = run_exhaustive_tests()
    sys.exit(0 if success else 1)
