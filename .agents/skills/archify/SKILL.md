---
name: archify
description: 本專案專用的架構與契約視覺化 Skill。強制利用本機 Archify Node.js 程式化編譯引擎 (.archify-engine/archify/bin/archify.mjs) 進行幾何求解、碰撞檢測與 HTML 渲染。嚴禁 AI 手寫 SVG 坐標，確保產出人類高可讀性、零穿透、且 100% 忠實對應 Codebase 實體契約的互動圖表。
license: MIT
metadata:
  version: "2.17-engine-enforced"
  author: tt-a1i / Crawler-Project
---

# Archify 程式化視覺化規範

> **核心鐵律：**
> 1. **嚴禁 AI 手寫 HTML/SVG 幾何坐標**：所有圖表一律由本機 Archify 引擎（`node .archify-engine/archify/bin/archify.mjs`）自動求解與編譯。
> 2. **AI 只專注兩件事**：
>    - (a) 詳實閱讀原始碼，完整盤點所有實體節點與資料流契約（不漏掉主力/備援爬蟲、快取、日誌等分支）。
>    - (b) 撰寫符合 Schema 的語意 JSON 規格（Typed JSON IR）。
> 3. **由引擎程式碼保證品質**：利用 `bin/archify.mjs validate` 的 9 項幾何檢查自動排版避障，未通過前禁止交付。
> 4. **語言規範**：圖表內的所有標籤（Labels）、卡片（Cards）、檢視說明（Views）一律使用**繁體中文（台灣）**。

---

## 標準執行四步管線（Standard Execution Pipeline）

### 第一步：原始碼實體窮舉盤點（Reconnaissance & Inventory）
在動筆寫 JSON 之前，必須先以搜尋工具在 Codebase 中確認所有真實實體：
1. **進入點**：盤點 CLI 入口、Sidecar 程序、FastAPI / Web 介面。
2. **爬蟲與下載來源**：盤點所有站點整合（如 JavDB, Real-Debrid, Magnet 解析等）。
3. **資料流分支**：盤點日誌記錄、磁力連結排程、快取命中、檔案產出。
4. **禁止簡化**：嚴禁將多個具體模組籠統壓縮為單一概括方塊。

---

### 第二步：撰寫語意契約規格 JSON（Authoring JSON IR）
依需求選擇圖表型態，輸出 JSON 規格檔（例如 `contracts_workflow.json`）：

* **Workflow 模式（推薦，適用資料流與跨邊界調度）**：
  * 使用 `schema_version: 2`
  * 利用 `lanes`（泳道）區分邊界：用戶端、排程/調度層、爬蟲層、雲端下載/API、儲存層。
  * `col` 索引必須介於 `0..5` 之間。
  * `phases` 區間不可重疊。
  * `mainPath` 必須與 `edges` 的起始/終止路徑完全連續。
* **語言**：所有 `label`、`sublabel`、`tag`、`cards` 一律填寫繁體中文。

---

### 第三步：執行引擎內建幾何驗證（Engine Validation Gate）
執行本地 Archify 引擎進行 9 項幾何與排版檢查：

```bash
node .archify-engine/archify/bin/archify.mjs validate <type> <candidate.json> --quality showcase --json
```

* **通過標準**：必須 `ok: true`，回報 `errors: 0`、`warnings: 0` 且通過全部 9 項檢查（`orthogonal_arrows`, `label_route_clearance`, `relationship_crossings`, `container_border_runs` 等）。
* **若有錯誤**：閱讀引擎回傳的 `diagnostics`（例如 `ambiguous-corridor`, `overlap`, `mainPath mismatch`），修改 JSON 屬性（如調整 `fromSide`/`toSide`/`route`），重新執行驗證直到完全通過。

---

### 第四步：執行引擎交付渲染（Engine Delivery）
使用引擎編譯產出最終自包含 HTML：

```bash
node .archify-engine/archify/bin/archify.mjs deliver <type> <candidate.json> <output.html> --quality showcase --json
```

* 產出的 HTML 放置於任務指定位置。
* 該 HTML 自帶完整的互動式視圖切換（Views）、Signal-Flow 訊號流動動畫、深淺色主題切換與 PNG/SVG 匯出功能。
