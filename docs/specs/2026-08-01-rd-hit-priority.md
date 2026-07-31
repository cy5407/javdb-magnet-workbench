# RD 命中優先（送出前預判快取機率）規格

日期：2026-08-01　狀態：已與使用者對齊，待實作

## 1. 問題與目標

送到 Real-Debrid 的磁力若別人已上傳過，RD 會立刻回快取並產生 https 直連；否則
落入 pending，使用者得反覆等待與重試。目前 UI 沒有任何「哪一筆最可能命中」的
訊號，使用者只能靠肉眼挑選。

**目標**：在送出前，用本地規則預判每筆磁力的 RD 命中機率，並能一鍵把每個番號
收斂成最可能命中的那一筆。

**前提（重要）**：Real-Debrid 已於 2024 移除 `/torrents/instantAvailability`，
本專案 `realdebrid.py` 也沒有任何快取查詢端點。因此「送出前檢查」**必然是本地
啟發式判定，不是打 API 查詢**。規格內所有「命中機率」都是啟發式推測，不是保證。

## 2. 判定規則（使用者已確認）

### 2.1 高清定義（擴充既有 `isHd`）

`isHd(row)` 由「只看 tag」擴充為：

1. `row.name` 含解析度 token（`2160p?` / `1080p?` / `4k` / `uhd`，需非英數邊界）→ 高清
2. `row.tags` 含 `高清` 或 `hd`（不分大小寫）→ 高清
3. 其餘 → 非高清

**這是刻意的行為契約變更**：`filterRows` 的 `hd_only` 也會跟著採用新定義，
JavDB 漏打 `高清` tag 但檔名寫 1080p 的列會開始通過篩選。既有測試無一斷言
「檔名含 1080p 但無 tag → false」，故 baseline 不受影響；契約文件必須同步。

### 2.2 發布站前綴

```
RD_CACHE_PREFIXES = ["hhd800.com@", "489155.com@"]
```

比對方式：`row.name` 轉小寫後 `includes`（非 `startsWith`）——JavDB 有時渲染成
`[javdb.com]hhd800.com@ABC-123`，用 `startsWith` 會漏。硬編碼常數即可，本輪
**不做設定頁可編輯清單**（不動 Rust settings / sidecar）。

### 2.3 每列分類 `RdRowClass`

| class | 條件 | 徽章 | 意義 |
|---|---|---|---|
| `prefix_hd` | 有前綴 ∧ 高清 | `⚡高清` | RD 最可能已有快取 |
| `prefix_only` | 有前綴 ∧ 非高清 | `⚡` | 命中率高但畫質未確認 |
| `hd` | 無前綴 ∧ 高清 | `高清` | 靠最早上傳判斷 |
| `unknown` | 非上述，且 `tags` 為空 **且** `date` 為空 | 無 | 無 metadata 可判（手貼磁力） |
| `plain` | 其餘（有 metadata 但明確非高清） | 無 | 低機率且畫質不符 |

`unknown` 存在的理由：手貼磁力沒有 size/tags/date，把它判成「低機率」是假訊號
——缺 metadata ≠ 低畫質。

### 2.4 每組首選 `pickRdCandidate(rows)`

依序取第一個非空集合，組內以 **date 由早到晚** 排序：

1. `prefix_hd` → tier `prefix_hd`
2. `hd` → tier `hd_earliest`
3. 全組皆非高清 → 取「有前綴者優先，其次日期最早」→ tier `no_hd_fallback`（⚠）

- **date key**：`row.date.trim()`；空字串正規化為 `"9999-99-99"`。**必須**如此，
  否則空字串會字串比較成「最早」，讓無日期的列永遠奪冠——這是本規格最容易寫錯
  的一點，需有專門測試。
- **同日 tie-break**：呼叫端注入的比較器（magnetUtils 傳入「大小大者優先」），
  預設為輸入順序。這麼設計是為了讓 `rdPriority.ts` 保持 leaf（只 import
  `./types`），避免與 `magnetUtils.ts` 形成 import 循環。
- 空輸入 → `null`。

## 3. 模組分層（不得形成循環）

```
types.ts  ←  rdPriority.ts  ←  magnetUtils.ts  ←  App.svelte
```

### 3.1 新檔 `app/src/lib/rdPriority.ts`（leaf，只 import `./types`）

```ts
export const RD_CACHE_PREFIXES: readonly string[];
export type RdRowClass = "prefix_hd" | "prefix_only" | "hd" | "unknown" | "plain";
export type RdPickTier = "prefix_hd" | "hd_earliest" | "no_hd_fallback";
export interface RdCandidate { row: MagnetRow; tier: RdPickTier }

export function hasCachePrefix(row: MagnetRow): boolean;
export function hasHdResolution(name: string): boolean;
export function isHdRow(row: MagnetRow): boolean;      // tag ∨ 解析度
export function rdDateKey(row: MagnetRow): string;      // "" → "9999-99-99"
export function classifyRow(row: MagnetRow): RdRowClass;
export function rdBadge(cls: RdRowClass): { text: string; title: string } | null;
export function pickRdCandidate(
  rows: MagnetRow[],
  tieBreak?: (a: MagnetRow, b: MagnetRow) => number,   // <0 = a 較佳
): RdCandidate | null;
export function summarizeRdLikelihood(classes: RdRowClass[]): {
  high: number;      // prefix_hd + hd
  low: number;       // plain
  unrated: number;   // prefix_only + unknown
};
```

Regex 需有界量詞（Sonar 對 super-linear backtracking 會告警），比照
`magnetUtils.ts` 既有 `SIZE_*_RX` 的寫法與註解風格。

### 3.2 `app/src/lib/magnetUtils.ts`

- `isHd(row)` 改為 `tags 命中 || hasHdResolution(row.name)`（見 §2.1）。
- 新增 `export function pickRdReadyRow(rows: MagnetRow[]): RdCandidate | null`
  ＝ `pickRdCandidate(rows, (a, b) => parseSizeGb(b.size) - parseSizeGb(a.size))`。
- `applyGroupPick` 新增 `rd_ready` 分支 → `pickRdReadyRow(rows)` 的 row 單元素陣列。
- 其餘策略行為一字不改。

### 3.3 `app/src/lib/types.ts`

`GroupPick` 增加 `"rd_ready"`。`defaultFilterState()` 仍為 `"all"`（預設不改變
既有使用者行為）。

### 3.4 `app/src/App.svelte`

1. **下拉選單**「每組只留」新增 `<option value="rd_ready">RD 命中優先</option>`，
   置於「全部」之後。
2. **候選推導**：
   ```ts
   function rdConsideredRows(g): MagnetRow[]   // manual → 原列；web → filterRows(...)
   let rdCandidates = $derived...              // [{ group, candidate }]
   let rdPickedHandles = $derived(Set<handle_id>)
   let rowClassByHandle = $derived(Map<handle_id, RdRowClass>)
   ```
   `rdConsideredRows` 必須與 `processGroupRows` 看到的集合一致（manual 跳過
   filter，web 先套 `filterRows`），否則星號會標在被篩掉的列上。
3. **每列徽章**：在番號欄顯示 `rdBadge(classifyRow(m))`（有則顯示，附 `title`
   說明理由），並在該組首選列加 `★`（`title` 說明 tier 理由）。
4. **一鍵按鈕**「只勾選 RD 優先候選」置於「只勾選目前顯示」旁：
   - 只作用於 **web 群組**：先取消 web 列勾選，再勾選 tier ≠ `no_hd_fallback`
     的候選。**手貼（manual）列的勾選狀態一律不動**——既有不變量是「手貼磁力
     是明確指令」（見 `registerPastedMagnets` 註解），不得被自動取消。
   - `statusMessage` 需回報：勾選幾筆、幾組因無高清候選被跳過、手貼列維持原狀。
5. **送出前攔截**：`sendSelectedToRd()` 先算 `summarizeRdLikelihood`：
   - `low === 0` → 維持現行行為，直接送出（避免對無可議之處的批次強制多一步）。
   - `low > 0` → 設 `pendingSendPlan`，畫面顯示摘要面板（高機率 N／低機率 M／
     未判定 K）與三個動作：**全部送出**、**只送高機率**、**取消**。實際送出邏輯
     抽成 `runSendBatch(items)`，兩個確認動作共用。
   - `pendingSendPlan` 在送出開始、取消、`clearResults` 時清空。

## 4. 測試要求

- 新檔 `app/src/lib/rdPriority.test.ts`：涵蓋前綴大小寫／內嵌前綴、解析度 token
  邊界（`1080MB` 不得誤判、`1080p`／`4K`／`UHD` 須命中）、`rdDateKey` 空值正規化
  （**必須有一筆「無日期列不得被選為最早」的 Red 測試**）、三層 tier 的選取、
  tie-break 注入、空輸入、`classifyRow` 五種分類、`summarizeRdLikelihood` 分桶。
- `magnetUtils.test.ts`：新增 `rd_ready` 的 `applyGroupPick` / `processGroupRows`
  案例（含 manual 群組跳過 group-pick 的既有行為不變）、`isHd` 擴充後的新案例。
- `App.test.ts`：新增（a）「只勾選 RD 優先候選」不動手貼列、（b）低機率存在時
  送出被攔截且「只送高機率」只送高機率那批、（c）全高機率時不攔截直接送出。
- **既有測試不得刪除或弱化**。若有既有期待改變，須在交付摘要寫明「舊期待／Red
  原因／新期待」。

## 5. 驗收（機器可判定）

```
cd app && npx vitest run                       # 全綠
cd app && npm run check                        # 0 errors 0 warnings
.venv/bin/python -m pytest tests/ -q           # baseline 全綠（本輪不動 Python）
```

Rust gate（`cargo test --lib`）baseline 本機即失敗（缺 Linux sidecar binary、
`secret-service` feature 問題），本輪不動 Rust，故跳過並於回報註明。

## 6. 契約文件同步（必做）

- `docs/architecture/contracts/frontend-lib.md`：新增 `rdPriority.ts` 章節與
  公開 API 表列；更新 `GroupPick`（新增 `rd_ready`）、`isHd`（擴充定義）、
  `applyGroupPick`（新分支）、`magnetUtils` API 表（新增 `pickRdReadyRow`）、
  §1.2 依賴圖與 §1.3 API surface。
- `docs/architecture/contracts/app-svelte.md`：新增狀態（`pendingSendPlan`）、
  推導（`rdCandidates` / `rdPickedHandles` / `rowClassByHandle`）與函式
  （`rdConsideredRows`、`selectRdCandidatesOnly`、`runSendBatch`、`confirmSend`）。
- `docs/architecture/function-contracts.md`：若列有 magnetUtils/App 函式索引則同步。
- 既有文件行號早已與程式碼漂移；本輪**只更新所觸碰段落**，不做全域行號重整。

## 7. 非目標

- 不打 RD API 做快取查詢（端點已不存在）。
- 不做設定頁可編輯前綴清單。
- 不動 Rust、sidecar、Python 任一層。
- 不改 `defaultFilterState()` 預設值。
