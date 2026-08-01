#!/usr/bin/env python3
"""從 rd_outcomes.jsonl 算出「哪些送出前訊號真的預測得到 RD 快取命中」。

用法：
    python scripts/rd_log_report.py [--log PATH] [--threshold-ms 5000]
                                    [--min-n 10] [--include-repeats]

規格：docs/specs/2026-08-01-rd-outcome-log.md

分工（§2）：日誌只存觀測，**假設全部寫在這裡**。下面的前綴清單與解析度正則是
分析用的一份獨立副本，與 app/src/lib/rdPriority.ts 的產品規則刻意分離 —— 你要
檢驗「換一條規則會不會更準」，改的就是這個檔案，而既有日誌不必重跑也不必轉檔。
兩邊哪天不一致不是 bug，是這個設計的用途。
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# ---- 待檢驗的假設（analysis-side copy，見 docstring）----------------------
CACHE_PREFIXES = ["hhd800.com@", "489155.com@"]
# `(?<=\dx)` 是定寬 lookbehind —— Python 的 re 不接受 `\d{1,4}x` 那種變寬形式。
# 行為與產品端等價：決定成敗的只有「1080 前面緊鄰的是 x，且 x 前面是數字」。
HD_RESOLUTION_RX = re.compile(r"(?:2160p|1080p|4k|uhd|(?<=\dx)(?:2160|1080))(?![a-z0-9])",
                              re.IGNORECASE)
HD_TAGS = {"高清", "hd"}

# 低於這個樣本數就不下結論。命中率在 n=3 時毫無意義，而一張沒有標註樣本數的
# 表格會讓人把雜訊當訊號。
DEFAULT_MIN_N = 10
# completed 但耗時超過這個門檻，代表 RD 是在我們等待期間才下載完的 —— 對使用者
# 而言那是「等了」，不是「秒回」。門檻可調，因為它取決於你的網路與 cache_wait。
DEFAULT_THRESHOLD_MS = 5000

# realdebrid._raise_if_terminal_failure 只在這兩種 RD 終態丟例外，它們代表
# 「RD 端這個磁力拿不到檔案」——對使用者等同「沒人有」，規格 §3 明文歸入 miss。
# 其餘 error（token 過期、429、API 5xx）與磁力本身無關：把它們算進分母會讓
# 環境問題看起來像「這個磁力沒人有」，所以留在分母外並單獨報數。
TERMINAL_FAILURE_CODES = {"rd_magnet_error", "rd_download_failed"}

LABELS = ("hit", "slow", "miss")
_UNSET = object()

LABEL_ZH = {"hit": "秒回", "slow": "慢但完成", "miss": "沒人有"}


def load_events(path: Path) -> list[dict]:
    """讀主檔與所有輪替備份（.1/.2/.3），跳過壞行。

    輪替備份必須一起讀，否則樣本會在檔案滿 5 MiB 時無聲消失一大塊。
    """
    files = [path] + sorted(
        path.parent.glob(path.name + ".*"),
        key=lambda p: p.name,
    )
    events: list[dict] = []
    for f in files:
        if not f.exists():
            continue
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                continue          # 輪替切斷的半行等
            if isinstance(obj, dict) and obj.get("event"):
                events.append(obj)
    return events


def _parse_ts(raw: Any) -> Optional[datetime]:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def label_sends(events: list[dict], threshold_ms: int) -> list[dict]:
    """把 send 事件貼上三元標籤，用 check 事件補完 pending 的結局。

    三元而非二元的理由：`completed` 混了「RD 本來就有」與「RD 在我們等待期間
    下載完」，而分界線是 cache_wait 設定值 —— 只看 outcome 欄位，同一個 magnet
    在不同設定下會被歸到不同類。
    """
    # torrent_id -> 最晚一次 completed check 的時間。保留時間是必要的：只存
    # id 的話，任何一次 completed check 都能把「時間更晚的」send 救成 slow。
    completed_checks: dict[str, Optional[datetime]] = {}
    for e in events:
        if e.get("event") == "check" and e.get("outcome") == "completed":
            tid = e.get("torrent_id") or ""
            if not tid:
                continue
            ts = _parse_ts(e.get("ts"))
            prev = completed_checks.get(tid, _UNSET)
            if prev is _UNSET or (ts is not None and (prev is None or ts > prev)):
                completed_checks[tid] = ts

    out: list[dict] = []
    for e in events:
        if e.get("event") != "send":
            continue
        outcome = e.get("outcome")
        if outcome == "error":
            # 終態失敗 = RD 拿不到這個磁力 = 沒人有。環境錯誤則不可歸因。
            label = "miss" if e.get("error_code") in TERMINAL_FAILURE_CODES else "error"
        elif outcome == "completed":
            elapsed = e.get("elapsed_ms")
            # 缺欄位或非數字一律當「不是秒回」。舊版當成 0（→ hit）是錯的方向：
            # 這份報表唯一的產出就是命中率，容錯不該往灌高的那一邊倒。
            label = ("hit" if isinstance(elapsed, (int, float))
                     and not isinstance(elapsed, bool)
                     and elapsed < threshold_ms else "slow")
        else:
            tid = e.get("torrent_id") or ""
            label = "miss"
            if tid and tid in completed_checks:
                # 只有「不早於這次 send」的 check 才算把它救回來。
                check_ts = completed_checks[tid]
                send_ts = _parse_ts(e.get("ts"))
                if check_ts is None or send_ts is None:
                    label = "slow"          # 時間不可解析 → 退回舊行為
                else:
                    try:
                        label = "slow" if check_ts >= send_ts else "miss"
                    except TypeError:
                        label = "slow"      # naive/aware 混用
        row = dict(e)
        row["label"] = label
        out.append(row)
    return out


def dedupe_first_per_btih(rows: list[dict]) -> tuple[list[dict], int]:
    """每個 btih8 只採計最早的一次觀測。

    第二次送出同一個 magnet 必定命中 —— 因為第一次是使用者自己把它放進 RD 的。
    不排除的話，愛用的片子會系統性地把命中率灌高。btih8 為空（無法解析）的列
    一律保留，因為它們彼此無法判定是否重複。
    """
    rows_sorted = sorted(rows, key=lambda r: (r.get("ts") or ""))
    seen: set[str] = set()
    kept: list[dict] = []
    dropped = 0
    for r in rows_sorted:
        key = r.get("btih8") or ""
        if key:
            if key in seen:
                dropped += 1
                continue
            seen.add(key)
        kept.append(r)
    return kept, dropped


# ---- 訊號抽取：從原始觀測還原成待檢驗的維度 -------------------------------

def sig_prefix(row: dict) -> str:
    """哪一個轉載站前綴命中。**分開記**，因為兩站的命中率可能不同 ——
    合併成一個 boolean 就永遠看不出其中一個其實沒用。"""
    name = (row.get("name") or "").lower()
    for p in CACHE_PREFIXES:
        if p in name:
            return p
    return "(無前綴)"


def sig_hd_source(row: dict) -> str:
    """HD 是靠 JavDB tag 判定還是靠檔名解析度判定。

    分開的理由同上：若檔名判定的預測力明顯較差，那條規則就該收緊或棄用，
    而合併成 is_hd 之後這個訊息就消失了。順序比照產品端 isHdRow（tag 優先）。
    """
    tags = row.get("tags") or []
    if any(isinstance(t, str) and t.lower() in HD_TAGS for t in tags):
        return "tag"
    if HD_RESOLUTION_RX.search(row.get("name") or ""):
        return "檔名解析度"
    return "非高清"


def sig_date_rank(row: dict) -> str:
    """「越早上傳越可能被快取」這個假設的直接檢驗。"""
    r = row.get("date_rank")
    if r == 1:
        return "組內最早"
    if isinstance(r, int):
        return f"組內第 {r} 早"
    return "(無群組)"


def sig_size_rank(row: dict) -> str:
    r = row.get("size_rank")
    if r == 1:
        return "組內最大"
    if isinstance(r, int):
        return f"組內第 {r} 大"
    return "(無群組)"


def sig_age_bucket(row: dict) -> str:
    """送出當下距 JavDB 上傳日的天數。刻意在分析時才算 —— 寫死在日誌裡的
    age 會在你隔月重跑報表時變成錯的。"""
    ts = _parse_ts(row.get("ts"))
    date_raw = row.get("date") or ""
    if ts is None or not date_raw:
        return "(無日期)"
    try:
        d = datetime.fromisoformat(date_raw)
    except ValueError:
        return "(無日期)"
    if d.tzinfo is None and ts.tzinfo is not None:
        d = d.replace(tzinfo=ts.tzinfo)
    days = (ts - d).days
    for edge, name in ((7, "0-7 天"), (30, "8-30 天"), (90, "31-90 天"), (365, "91-365 天")):
        if days < edge:
            return name
    return "365 天以上"


def sig_source(row: dict) -> str:
    return row.get("source") or "(未知)"


DIMENSIONS = [
    ("轉載站前綴", sig_prefix),
    ("HD 判定來源", sig_hd_source),
    ("組內上傳順位", sig_date_rank),
    ("組內大小順位", sig_size_rank),
    ("上傳距今", sig_age_bucket),
    ("來源", sig_source),
]


def _width(s: str) -> int:
    """終端顯示寬度。CJK 是雙寬，用 len() 排版會讓整張表歪掉。"""
    import unicodedata
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in s)


def _pad(s: str, width: int, right: bool = False) -> str:
    fill = " " * max(0, width - _width(s))
    return fill + s if right else s + fill


def tabulate(rows: list[dict], keyfn, min_n: int) -> list[str]:
    buckets: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in rows:
        buckets[keyfn(r)][r["label"]] += 1

    cols = (("值", 18), ("n", 5), ("秒回", 8), ("慢但完成", 10), ("沒人有", 8))
    header = "  " + "".join(
        _pad(name, w, right=(i > 0)) + "  " for i, (name, w) in enumerate(cols)
    ) + "備註"
    lines = [header, "  " + "-" * (_width(header) - 2)]
    for key in sorted(buckets, key=lambda k: -sum(buckets[k][x] for x in LABELS)):
        counts = buckets[key]
        n = sum(counts[x] for x in LABELS)
        if n == 0:
            continue
        cells = [(key, False)] + [(str(n), True)] + [
            (f"{counts[x] / n * 100:.1f}%", True) for x in LABELS
        ]
        note = "" if n >= min_n else f"樣本不足（<{min_n}），不下結論"
        lines.append(
            "  " + "".join(_pad(v, w, right=r) + "  "
                           for (v, r), (_, w) in zip(cells, cols)) + note
        )
    return lines


def build_report(events: list[dict], threshold_ms: int, min_n: int,
                 include_repeats: bool) -> str:
    labeled = label_sends(events, threshold_ms)
    errors = [r for r in labeled if r["label"] == "error"]
    scored = [r for r in labeled if r["label"] in LABELS]

    dropped = 0
    if not include_repeats:
        scored, dropped = dedupe_first_per_btih(scored)

    out: list[str] = []
    out.append("RD 送出成效報表")
    out.append("=" * 72)
    out.append(f"事件總數 {len(events)}；送出 {len(labeled)}；納入統計 {len(scored)}；"
               f"環境錯誤 {len(errors)}（token／速率限制／API 錯誤，與磁力無關，"
               f"不計入命中率；磁力終態失敗已計入「沒人有」）")
    if errors:
        codes = defaultdict(int)
        for r in errors:
            codes[r.get("error_code") or "(無碼)"] += 1
        out.append("  環境錯誤明細：" + "、".join(
            f"{k} {v}" for k, v in sorted(codes.items(), key=lambda kv: -kv[1])))
    if dropped:
        out.append(f"已排除重複送出的同一 magnet {dropped} 筆 —— 第二次必定命中，"
                   f"因為第一次是你自己放進 RD 的（--include-repeats 可保留）")
    out.append(f"「秒回」門檻：elapsed_ms < {threshold_ms}")
    out.append("")

    if not scored:
        out.append("沒有可統計的樣本。先用 app 送出幾批，再回來看這份報表。")
        return "\n".join(out)

    total = len(scored)
    counts = defaultdict(int)
    for r in scored:
        counts[r["label"]] += 1
    out.append("整體：" + "　".join(
        f"{LABEL_ZH[x]} {counts[x]}（{counts[x] / total * 100:.1f}%）" for x in LABELS))
    out.append("")

    for title, fn in DIMENSIONS:
        out.append(f"■ {title}")
        out.extend(tabulate(scored, fn, min_n))
        out.append("")

    # 選擇偏誤警告。一鍵勾選會把送出收斂到 ★ 首選，若使用者只送推薦的那筆，
    # 「非高清」類就永遠沒有樣本 —— 那張表看起來很漂亮，但它無法證偽推薦規則。
    non_hd = sum(1 for r in scored if sig_hd_source(r) == "非高清")
    no_prefix = sum(1 for r in scored if sig_prefix(r) == "(無前綴)")
    warns = []
    if non_hd < min_n:
        warns.append(f"「非高清」只有 {non_hd} 筆樣本")
    if no_prefix < min_n:
        warns.append(f"「無前綴」只有 {no_prefix} 筆樣本")
    if warns:
        out.append("⚠ 選擇偏誤警告：" + "、".join(warns) + "。")
        out.append("  沒有對照組就無法證明推薦規則有效 —— 你只會看到推薦那類的命中率，")
        out.append("  卻不知道隨便挑一個是不是也一樣高。偶爾走「全部送出」而不是")
        out.append("  「只送高機率」，日誌才會累積到對照樣本。")

    return "\n".join(out)


def default_log_path() -> Optional[Path]:
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from app_logging import _candidate_log_dirs  # type: ignore
    except Exception:
        return None
    for d in _candidate_log_dirs():
        p = d / "rd_outcomes.jsonl"
        if p.exists():
            return p
    return None


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="RD 送出成效報表")
    ap.add_argument("--log", type=Path, default=None,
                    help="rd_outcomes.jsonl 路徑（預設自動尋找 log 目錄）")
    ap.add_argument("--threshold-ms", type=int, default=DEFAULT_THRESHOLD_MS,
                    help=f"「秒回」的耗時門檻（預設 {DEFAULT_THRESHOLD_MS}）")
    ap.add_argument("--min-n", type=int, default=DEFAULT_MIN_N,
                    help=f"低於此樣本數即標示不下結論（預設 {DEFAULT_MIN_N}）")
    ap.add_argument("--include-repeats", action="store_true",
                    help="保留重複送出的同一 magnet（預設排除，避免自造命中灌水）")
    args = ap.parse_args(argv[1:])

    path = args.log or default_log_path()
    if path is None or not Path(path).exists():
        print("找不到 rd_outcomes.jsonl。請用 --log 指定路徑，"
              "或先在 app 送出幾批以產生日誌。", file=sys.stderr)
        return 1

    events = load_events(Path(path))
    print(build_report(events, args.threshold_ms, args.min_n, args.include_repeats))
    return 0


if __name__ == "__main__":  # pragma: no cover — script entry guard
    sys.exit(main(sys.argv))
