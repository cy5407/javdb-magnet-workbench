---
trigger: always_on
description: 禁止遞迴刪除鐵律。禁止遞迴與破壞性刪除，允許單檔逐一刪除。
---

# 禁止遞迴刪除鐵律 (Prohibit Recursive Deletion)

## 核心規則
禁止遞迴刪除，允許單檔逐一刪除。

### 禁止動作（由 Hook 硬性阻擋）
- POSIX / Bash：遞迴刪除旗標（-r, -rf, --recursive）、trash -r、find 配合刪除。
- PowerShell：Remove-Item / rm / del / rd / ri / rmdir 帶 -Recurse（含縮寫）。
- Pipeline 遞迴：Get-ChildItem 遞迴列舉後接刪除。
- Git：git 遞迴移除（git rm 帶 -r）、工作樹抹除、未保護的清理（git clean 強制旗標）、強制工作區抹除重設。
- 語言庫：shutil 遞迴樹刪除、fs 遞迴刪除、Directory.Delete 帶 true、rimraf 等套件。
- 鏡像清空：robocopy 帶 /MIR 或 /PURGE。

### 允許動作
- 單檔刪除：rm file.txt、Remove-Item log.txt、del app.log。
- 需要清空目錄時，逐一列出檔案後單檔刪除，不使用遞迴旗標。
