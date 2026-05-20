# Task: P1.2 — Bump Python sidecar 依賴修 5 個 CVE

## 修改範圍

只允許修改：
- `requirements-sidecar.txt`
- `requirements-ci.txt`

**禁止**：其他檔、`git commit`、`pip install`、執行 PyInstaller（這些由 reviewer 後續手動驗證）。

## 改動

### A. `requirements-sidecar.txt`

定位這三行（line 15、16、23）並修改 pin：

```
curl_cffi==0.14.0          → curl_cffi>=0.15.0,<1.0
requests==2.32.5           → requests>=2.33.0,<3.0
urllib3==2.6.3             → urllib3>=2.7.0,<3.0
```

說明用 `>=X.Y.0,<MAJOR+1.0` 而非鎖死特定版本：
- 讓 pip 拉到 `0.15.0` 或更新的 patch 版（含同/後 patch CVE 修補）
- 上限 cap 在下一個 major（避免 breaking change 自動進來）

### B. `requirements-ci.txt`

定位 line 7：

```
pytest==8.3.4              → pytest>=9.0.3,<10.0
```

### C. 保留事項（不要動）

- 不要動既有 `chardet==5.2.0` / `charset-normalizer==3.4.4` / `idna==3.11` / `certifi==2026.1.4`（這些是 transitive，與 CVE 無關）
- 不要動檔頭的 comment block（pyinstaller==6.19.0 / beautifulsoup4 等）
- 不要新增 deps

## 驗證

```
python output/verify-deps-bumped.py
```

該 helper script 會檢查：
1. `requirements-sidecar.txt` 不再含 `curl_cffi==0.14.0`、`requests==2.32.5`、`urllib3==2.6.3` 三個舊 pin
2. `requirements-sidecar.txt` 含 `curl_cffi>=0.15.0`、`requests>=2.33.0`、`urllib3>=2.7.0` 新 pin
3. `requirements-ci.txt` 不再含 `pytest==8.3.4`，含 `pytest>=9.0.3`

不需要實際跑 `pip install` 或 PyInstaller（這由 reviewer 後續手動驗證 bundle）。

## 範圍提醒

- 只動 2 個 requirements 檔
- 0 git op
- 不要碰 sidecar/sidecar.py 或 realdebrid.py 的呼叫端
