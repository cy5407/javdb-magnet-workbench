# Task: P2.4 + P2.5 — 兩個 config 一致性修補

## 修改範圍

只允許修改：
- `app/src-tauri/Cargo.toml`
- `app/src-tauri/tauri.conf.json`

**禁止**：其他檔、`git commit` / `add` / `push` / `reset` / `checkout` / `stash`。

## P2.5：Cargo.toml keyring 跨 OS features

### 問題

`Cargo.toml:31` 目前：
```toml
keyring = { version = "3", features = ["windows-native"] }
```

但 line 29-30 註解寫：
> `apple-native` / `linux-native-async-persistent` enable the equivalent secure stores on the other targets

→ 註解描述跟實際 features 不一致。`path_manager.rs:37` 有 `#[cfg(not(target_os = "windows"))]` fallback 路徑，配上沒有 backend 的 keyring 會 runtime panic。

### 修法

把 features 改成跨 OS 三個都啟用（最簡修法，對齊既有註解）：

```toml
keyring = { version = "3", features = ["windows-native", "apple-native", "linux-native-async-persistent"] }
```

### 不要做的事

- 不要 reformat 其他 deps
- 不要動 Cargo.toml 的 `[package]` / `[features]` 區段
- 不要動其他 dep 版本

## P2.4：tauri.conf.json targets 與 portable-zip 策略一致

### 問題

`tauri.conf.json:29`：
```json
"targets": ["msi"],
```

但日常 release 走 `tauri build --no-bundle` + portable zip（你 audit 過的 artifact）。MSI installer 是不同二進位、不同分發路徑、不同簽章狀態——容易混淆。

### 修法

把 `targets` 改成空陣列（不生 installer，跟 release pipeline 對齊）：

```json
"targets": [],
```

### 不要做的事

- 不要動 `"productName"` / `"icon"` / `"resources"` 等其他 bundle 設定
- 不要動 `csp` 那行（P2.1，另案處理）
- 不要動 `withGlobalTauri` 或 windows config

## 驗證

```
python output/verify-config-cleanup.py
```

該 helper 檢查：
1. Cargo.toml 第 31 行（keyring）含三個 features
2. tauri.conf.json line 29 targets 為空陣列 `[]`

不需要實際 `cargo build` 或 `tauri build`——reviewer 後續手動驗證。

## 範圍提醒

- 只動 2 個 config 檔
- 0 git op
