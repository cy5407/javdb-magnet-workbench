# Task: 兩個 P2 小修（operator precedence + clippy）

## 修改範圍（嚴格限制）

只允許修改這兩個檔：

- `sidecar/sidecar.py`
- `app/src-tauri/src/commands.rs`

**禁止**修改任何其他檔案、**禁止** `git commit` / `git add` / `git push` / `git reset` / `git checkout` / `git stash`。

## A. sidecar/sidecar.py — 加括號釐清 operator precedence

### A1. Line 512

目前是：
```python
if "401" in m or "token 無效" in m or "token" in m and "過期" in m:
```

`and` 比 `or` 優先，**實際行為 = `A or B or (C and D)`**，跟作者意圖一致，但讀者第一眼會看錯。

改成：
```python
if "401" in m or "token 無效" in m or ("token" in m and "過期" in m):
```

### A2. Line 516

目前是：
```python
if "429" in m or "rate" in m and "limit" in m:
```

改成：
```python
if "429" in m or ("rate" in m and "limit" in m):
```

### A3. 嚴格不准做的事

- 不要動該 function 的其他行
- 不要改 indent / quote 形式
- 不要把 lower-case match 改寫
- 不要加新 case（即使你覺得「順便補一條會更好」）

## B. app/src-tauri/src/commands.rs — clippy unneeded return

### B1. Line 1038

定位該行（位於 `#[cfg(target_os = "windows")]` block 末尾）：

```rust
            .arg(p.as_os_str())
            .spawn()
            .map_err(|e| format!("spawn explorer: {e}"))?;
        return Ok(());
    }
```

`return Ok(());` 是該 block 最後一個 expression，clippy 警告 unneeded `return`。

改成：
```rust
            .arg(p.as_os_str())
            .spawn()
            .map_err(|e| format!("spawn explorer: {e}"))?;
        Ok(())
    }
```

（刪掉 `return ` 跟結尾分號）

### B2. 嚴格不准做的事

- 不要動 `#[cfg(not(target_os = "windows"))]` 那段 fallback
- 不要 reformat 函式其他行
- 不要 import 新東西

## 驗證命令（supervisor 會跑）

完成後以下必須 pass：

```
python -m py_compile sidecar/sidecar.py
```

`cargo clippy` 不在 verify 範圍（太慢），由 reviewer 後續手動確認。

## 範圍提醒

- 只改上述 2 個檔的指定行
- 0 個其他變動
- 不 commit / 不 push
- 完成後 working tree 應該只有這兩個檔被 modified
