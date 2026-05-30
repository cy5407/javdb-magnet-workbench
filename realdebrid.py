"""Real-Debrid API 模組

文件：https://api.real-debrid.com/
"""

import time
from pathlib import Path
from typing import Callable, Optional

import requests

from app_logging import get_logger

logger = get_logger(__name__)

API_BASE = "https://api.real-debrid.com/rest/1.0"
VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".wmv", ".mov", ".m4v", ".ts", ".webm"}


class RealDebridError(Exception):
    pass


class RealDebrid:
    def __init__(self, token: str, min_size_mb: int = 500):
        if not token:
            raise RealDebridError("RD_API_TOKEN 未設定，請編輯 .env 檔案貼上 token")
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Bearer {token}"
        self.min_size_mb = min_size_mb

    def _request(self, method: str, path: str, _retry_count: int = 0, **kwargs):
        url = f"{API_BASE}{path}"
        logger.debug(f"→ {method} {path} {self._redact_log_kwargs(kwargs)}")

        resp = self.session.request(method, url, timeout=30, allow_redirects=False, **kwargs)
        logger.debug(f"← HTTP {resp.status_code} ({len(resp.content)} bytes)")

        if resp.status_code == 429:
            return self._retry_after_rate_limit(resp, method, path, _retry_count, kwargs)

        self._raise_for_status(resp)

        if resp.status_code == 204 or not resp.content:
            return None
        result = resp.json()
        self._log_torrent_info_summary(result)
        return result

    _SENSITIVE_HEADERS = ("authorization", "proxy-authorization", "cookie")

    @staticmethod
    def _truncate(value, limit: int = 80) -> str:
        s = str(value)
        return s[:limit] + "..." if len(s) > limit else s

    @staticmethod
    def _redact_data_field(key: str, value) -> str:
        return "<redacted>" if key == "magnet" else RealDebrid._truncate(value)

    @staticmethod
    def _redact_header_field(name: str, value) -> str:
        # case-insensitive match; any header that authenticates the
        # request gets fully redacted (don't even keep the prefix).
        if name.lower() in RealDebrid._SENSITIVE_HEADERS:
            return "<redacted>"
        return RealDebrid._truncate(value)

    @staticmethod
    def _redact_log_kwargs(kwargs: dict) -> dict:
        """產生 debug log 用的 kwargs；magnet / Authorization 全遮蔽，其餘欄位 80 字截斷。
        實際送出的 kwargs 不變。

        Bearer token 平時掛在 ``self.session.headers["Authorization"]``，不會出現
        在每個 ``_request`` 的 kwargs 裡——但如果未來有人在 ``_request`` 加上
        ``headers=`` per-request override，這條 defense-in-depth 確保 Authorization
        值不會洩進 debug log（F-09 / Authorization redaction）。
        """
        log: dict = {}
        if "data" in kwargs:
            log["data"] = {k: RealDebrid._redact_data_field(k, v) for k, v in kwargs["data"].items()}
        if "headers" in kwargs:
            log["headers"] = {k: RealDebrid._redact_header_field(k, v) for k, v in kwargs["headers"].items()}
        return log

    def _retry_after_rate_limit(self, resp, method: str, path: str, retry_count: int, kwargs: dict):
        """429 自動重試（最多 3 次）"""
        if retry_count >= 3:
            logger.error("429 重試 3 次仍失敗")
            raise RealDebridError("HTTP 429: 請求頻率過高，請稍後再試")
        wait = self._parse_retry_after(resp)
        logger.warning(f"429 速率限制，等待 {wait}s 後重試（第 {retry_count + 1}/3 次）")
        time.sleep(wait)
        return self._request(method, path, _retry_count=retry_count + 1, **kwargs)

    @staticmethod
    def _raise_for_status(resp) -> None:
        """非 2xx 一律轉成 RealDebridError；401/403 給出特定訊息。"""
        if resp.status_code == 401:
            logger.error("API token 無效或已過期")
            raise RealDebridError("API token 無效或已過期")
        if resp.status_code == 403:
            logger.error("帳號權限不足")
            raise RealDebridError("帳號權限不足（需要 Premium 會員）")
        if 300 <= resp.status_code < 400:
            logger.error(f"HTTP {resp.status_code}: unexpected redirect")
            raise RealDebridError(f"HTTP {resp.status_code}: unexpected redirect")
        if resp.ok:
            return
        msg = None
        # JSON parse / type errors are intentional fall-through to generic "API error".
        try:
            body = resp.json()
            if isinstance(body, dict):
                err = body.get("error")
                if isinstance(err, str) and err:
                    msg = err[:80]
        except Exception:  # nosec B110
            pass
        if msg is None:
            msg = "API error"
        logger.error(f"HTTP {resp.status_code}: {msg}")
        raise RealDebridError(f"HTTP {resp.status_code}: {msg}")

    @staticmethod
    def _log_torrent_info_summary(result) -> None:
        """對於 torrent_info，記錄重點欄位避免太冗長"""
        if not isinstance(result, dict) or "files" not in result:
            return
        logger.debug(
            f"  status={result.get('status')} progress={result.get('progress')} "
            f"files={len(result.get('files', []))} links={len(result.get('links', []))}"
        )

    @staticmethod
    def _parse_retry_after(resp) -> float:
        """從回應 header 取得 Retry-After 秒數，沒給就用指數退避"""
        retry_after = resp.headers.get("Retry-After")
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                pass
        # 預設退避：5 秒
        return 5.0

    def add_magnet(self, magnet: str) -> str:
        """新增磁力，回傳 torrent id"""
        result = self._request("POST", "/torrents/addMagnet", data={"magnet": magnet})
        return result["id"]

    def torrent_info(self, torrent_id: str) -> dict:
        return self._request("GET", f"/torrents/info/{torrent_id}")

    def select_files(self, torrent_id: str, file_ids: list[int] | str = "all"):
        files_param = file_ids if isinstance(file_ids, str) else ",".join(str(i) for i in file_ids)
        self._request("POST", f"/torrents/selectFiles/{torrent_id}", data={"files": files_param})

    def delete_torrent(self, torrent_id: str):
        try:
            self._request("DELETE", f"/torrents/delete/{torrent_id}")
        except RealDebridError as e:
            logger.warning(f"delete_torrent 清理失敗: {torrent_id} - {e}")

    def unrestrict_link(self, link: str) -> dict:
        return self._request("POST", "/unrestrict/link", data={"link": link})

    @staticmethod
    def _extract_code(magnet: str) -> str | None:
        """從磁力的 dn= 參數抽出 JAV 番號（如 SNOS-192, IPZZ-851）"""
        import re as _re
        from urllib.parse import parse_qs, urlparse
        if not magnet:
            return None
        # urlparse + parse_qs 取代 r"dn=([^&]+)" — 那種 unbounded [^&]+ 會被
        # Sonar 認定為 polynomial backtracking。parse_qs 同時負責 `+`/`%XX`
        # 解碼，行為與原本 unquote(m.group(1)) 相同。
        parsed = urlparse(magnet)
        values = parse_qs(parsed.query, keep_blank_values=True).get("dn")
        if not values:
            return None
        name = values[0]
        # 比對 ABCD-1234 / ABCDEF-12345 等格式（2-6 字母 + 3-5 數字）
        code_match = _re.search(r"\b([A-Za-z]{2,6})[-_]?(\d{3,5})\b", name)
        if code_match:
            return f"{code_match.group(1).upper()}-{code_match.group(2)}"
        return None

    @staticmethod
    def _filename_matches_code(filename: str, code: str) -> bool:
        """檔名是否含番號（容忍大小寫、底線/橫線、有無分隔符）"""
        if not code:
            return False
        name = filename.upper().replace("_", "-")
        code_up = code.upper()
        # 接受 SNOS-192 或 SNOS192（去掉橫線）
        return code_up in name or code_up.replace("-", "") in name.replace("-", "")

    def pick_files(self, files: list[dict], strategy: str = "smart", magnet: str = "") -> list[int]:
        """根據策略決定要選哪些檔案，回傳 file id 清單"""
        if not files:
            return []
        if strategy == "all":
            return [f["id"] for f in files]
        if strategy == "video":
            return self._pick_video(files)
        if strategy == "smart":
            return self._pick_smart(files, magnet)
        return self._pick_largest(files)

    @staticmethod
    def _pick_video(files: list[dict]) -> list[int]:
        picked = [f for f in files if Path(f["path"]).suffix.lower() in VIDEO_EXTS]
        return [f["id"] for f in picked] or [max(files, key=lambda f: f["bytes"])["id"]]

    @staticmethod
    def _pick_largest(files: list[dict]) -> list[int]:
        """largest：只選最大的影片檔；如果沒影片副檔名就選最大檔"""
        videos = [f for f in files if Path(f["path"]).suffix.lower() in VIDEO_EXTS]
        candidates = videos if videos else files
        return [max(candidates, key=lambda f: f["bytes"])["id"]]

    def _pick_smart(self, files: list[dict], magnet: str) -> list[int]:
        min_bytes = self.min_size_mb * 1024 * 1024

        code = self._extract_code(magnet) if magnet else None
        if code:
            ids = self._smart_code_match(files, code, min_bytes)
            if ids:
                return ids

        ids = self._smart_size_filter(files, min_bytes)
        if ids:
            return ids

        logger.warning(f"smart 策略：沒有檔案 >= {self.min_size_mb}MB，退回選最大檔")
        return [max(files, key=lambda f: f["bytes"])["id"]]

    def _smart_code_match(self, files: list[dict], code: str, min_bytes: int) -> list[int]:
        code_matches = [
            f for f in files
            if Path(f["path"]).suffix.lower() in VIDEO_EXTS
            and self._filename_matches_code(Path(f["path"]).name, code)
        ]
        if not code_matches:
            logger.debug(f"smart 策略：番號 {code} 沒有檔名匹配，退回 size 門檻")
            return []
        size_filtered = [f for f in code_matches if f["bytes"] >= min_bytes]
        final = size_filtered if size_filtered else code_matches
        logger.info(
            f"smart 策略：番號 {code} 匹配 {len(code_matches)} 個影片檔，"
            f"套用 {self.min_size_mb}MB 門檻後保留 {len(final)} 個"
        )
        return [f["id"] for f in final]

    def _smart_size_filter(self, files: list[dict], min_bytes: int) -> list[int]:
        picked = [
            f for f in files
            if Path(f["path"]).suffix.lower() in VIDEO_EXTS and f["bytes"] >= min_bytes
        ]
        if not picked:
            return []
        logger.debug(f"smart 策略：size 門檻 {self.min_size_mb}MB，符合 {len(picked)}/{len(files)} 個")
        return [f["id"] for f in picked]

    def process_magnet(
        self,
        magnet: str,
        strategy: str = "smart",
        cache_wait: int = 15,
        progress: Optional[Callable[[str], None]] = None,
    ) -> dict:
        """加磁力 → 選檔案 → 等待 cache_wait 秒 → 判定快取狀態

        回傳格式：
        - 已快取：{"status": "completed", "name": ..., "torrent_id": ..., "links": [...]}
        - 未快取：{"status": "pending", "name": ..., "torrent_id": ..., "progress": ..., "rd_status": ...}

        注意：未快取或解析中（magnet_conversion）都會保留 RD 上的 torrent，回傳 pending
        只有 magnet_error 會真正刪除並丟出例外
        """
        def log(msg: str):
            logger.info(msg)
            if progress:
                progress(msg)

        magnet_hash = self._extract_magnet_hash(magnet)
        logger.info(f"=== 開始處理磁力 [{magnet_hash}] ===")

        log("新增磁力...")
        torrent_id = self.add_magnet(magnet)
        logger.info(f"取得 torrent id: {torrent_id}")

        log(f"等待解析檔案清單（最多 {cache_wait} 秒）...")
        deadline = time.time() + cache_wait
        info = None
        files_selected = False
        last_status = ""
        last_progress = 0

        while time.time() < deadline:
            info = self.torrent_info(torrent_id)
            last_status = info.get("status", "")
            last_progress = info.get("progress", 0)

            self._raise_if_terminal_failure(torrent_id, last_status, info)

            if last_status == "waiting_files_selection" and not files_selected:
                self._select_files_during_wait(torrent_id, info, strategy, magnet, log)
                files_selected = True
                continue

            if last_status == "downloaded":
                log("已快取，取得下載連結")
                results = self._collect_links(info)
                logger.info(f"=== 磁力 [{magnet_hash}] 已快取，{len(results)} 個連結 ===")
                return {
                    "status": "completed",
                    "name": info.get("filename", ""),
                    "torrent_id": torrent_id,
                    "links": results,
                }

            time.sleep(3)

        return self._build_pending_result(
            info, torrent_id, last_status, last_progress,
            files_selected, magnet_hash, log,
        )

    @staticmethod
    def _extract_magnet_hash(magnet: str) -> str:
        """從磁力中抽出 BTIH hash 前 8 碼供 log 標記用；找不到時回傳 'unknown'。"""
        import re as _re
        # Bounded {1,128} 涵蓋 BTIH v1 (40 hex) 與 v2 (64 hex)，避免 Sonar
        # 對 unbounded `+` on `[a-fA-F0-9]` 的 super-linear 警告。
        m = _re.search(r"btih:([a-fA-F0-9]{1,128})", magnet)
        return m.group(1)[:8] if m else "unknown"

    def _raise_if_terminal_failure(self, torrent_id: str, status: str, info: dict) -> None:
        """magnet_error / error：刪除 torrent 並丟出對應例外。"""
        if status == "magnet_error":
            self.delete_torrent(torrent_id)
            raise RealDebridError(f"磁力解析失敗: {info.get('filename', '')}")
        if status == "error":
            self.delete_torrent(torrent_id)
            raise RealDebridError("下載失敗")

    @staticmethod
    def _format_picked_names(files: list[dict], picked: list[int]) -> str:
        picked_set = set(picked)
        return ", ".join(
            f"{Path(f['path']).name} ({f['bytes'] / 1024**3:.2f}GB)"
            for f in files if f["id"] in picked_set
        )

    def _select_files_during_wait(
        self, torrent_id: str, info: dict, strategy: str, magnet: str,
        log: Callable[[str], None],
    ) -> None:
        """waiting_files_selection 階段：列出檔案、套策略選檔、實際送 selectFiles。

        pick_files 結果為空時刪除 torrent 並丟出 RealDebridError。"""
        files = info.get("files", [])
        logger.debug(f"檔案清單 ({len(files)} 個):")
        for f in files:
            logger.debug(f"  id={f['id']} {Path(f['path']).name} ({f['bytes'] / 1024**3:.2f}GB)")
        picked = self.pick_files(files, strategy, magnet=magnet)
        if not picked:
            self.delete_torrent(torrent_id)
            raise RealDebridError("沒有可選的檔案")
        picked_names = self._format_picked_names(files, picked)
        log(f"選擇檔案 (策略={strategy}): {picked_names}")
        self.select_files(torrent_id, picked)

    @staticmethod
    def _build_pending_result(
        info: Optional[dict], torrent_id: str, last_status: str, last_progress,
        files_selected: bool, magnet_hash: str, log: Callable[[str], None],
    ) -> dict:
        """逾時或解析中：保留 RD torrent、組 pending 回傳。"""
        if not files_selected:
            log(f"解析中（{last_status}），加入待處理清單稍後重試")
        else:
            log(f"未快取（{last_status} {last_progress}%），加入待處理清單")
        logger.info(
            f"=== 磁力 [{magnet_hash}] 待處理 "
            f"(status={last_status}, files_selected={files_selected}) ==="
        )
        return {
            "status": "pending",
            "name": info.get("filename", "") if info else "",
            "torrent_id": torrent_id,
            "progress": last_progress,
            "rd_status": last_status,
            "files_selected": files_selected,
        }

    def check_torrent(self, torrent_id: str, strategy: str = "smart", magnet: str = "") -> dict:
        """查詢 torrent 目前狀態，必要時自動選檔案

        - 若狀態為 waiting_files_selection，會用指定策略自動選檔案再查一次
          （傳入 magnet 可讓 smart 策略使用番號比對）
        - 若已完成（downloaded），回傳 completed 與下載連結
        - 否則回傳 pending（含 RD 狀態與進度）
        - 找不到（404）回傳 missing
        """
        try:
            info = self.torrent_info(torrent_id)
        except RealDebridError as e:
            if "404" in str(e):
                logger.warning(f"torrent {torrent_id} 不存在於 RD")
                return {"status": "missing", "torrent_id": torrent_id}
            raise

        status = info.get("status", "")

        # 如果還沒選檔案，現在補選
        if status == "waiting_files_selection":
            files = info.get("files", [])
            picked = self.pick_files(files, strategy, magnet=magnet)
            if picked:
                picked_names = self._format_picked_names(files, picked)
                logger.info(f"重試時補選檔案 (策略={strategy}): {picked_names}")
                self.select_files(torrent_id, picked)
                # 立刻再查一次
                info = self.torrent_info(torrent_id)
                status = info.get("status", "")

        if status == "downloaded":
            results = self._collect_links(info)
            return {
                "status": "completed",
                "name": info.get("filename", ""),
                "torrent_id": torrent_id,
                "links": results,
            }
        return {
            "status": "pending",
            "name": info.get("filename", ""),
            "torrent_id": torrent_id,
            "progress": info.get("progress", 0),
            "rd_status": status,
        }

    def _collect_links(self, info: dict) -> list[dict]:
        """從 torrent info 取得所有 unrestrict 後的下載連結"""
        links = info.get("links", [])
        if not links:
            return []
        results = []
        for link in links:
            try:
                unrestricted = self.unrestrict_link(link)
                results.append({
                    "original": link,
                    "download": unrestricted.get("download", ""),
                    "filename": unrestricted.get("filename", ""),
                    "filesize": unrestricted.get("filesize", 0),
                    "streamable": unrestricted.get("streamable", 0),
                })
                logger.info(f"  ✓ {unrestricted.get('filename', '')} ({unrestricted.get('filesize', 0)} bytes)")
            except RealDebridError as e:
                logger.warning(f"  ✗ unrestrict 失敗: {link} - {e}")
                results.append({"original": link, "error": str(e)})
        return results
