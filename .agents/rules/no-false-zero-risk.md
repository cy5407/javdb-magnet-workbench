---
trigger: always_on
description: 破壞性操作真實風險與反假安全宣告準則。工作區 dirty 時嚴禁宣稱零風險，強制 stash -u。
---

# 破壞性操作真實風險與反假安全宣告準則 (No False Zero-Risk Claims)

## 1. 零風險宣告禁令
- 嚴禁對任何會抹除工作區的指令宣稱「零風險」。
- 涉及重設、強制還原或清理工作區時，必須先執行狀態檢查。若有未提交修改或未追蹤檔案，任何未保護的操作皆為「高風險／破壞性」操作。

## 2. 標準防破壞隔離 SOP (Stash-Before-Reset Invariant)
- 凡涉及分支切換、歷史覆蓋或清理工作區，唯一合法的保全指令是：
  git stash push -u -m "pre-op-backup: [description]"
- 必須帶 -u（--include-untracked），否則未追蹤檔案仍會被毀滅。
- 嚴禁使用底層 plumbing 指令（如 git update-ref）假裝完成切換。保持 HEAD、Index 與工作目錄三位一體完全同步。
