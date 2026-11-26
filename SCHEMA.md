# 知識庫結構與檢查規則（SCHEMA）

本知識庫整理「個人理財與指數投資入門（台灣新手視角）」，所有條目皆由 `raw/` 中的公開參考來源彙整而來，並經過三道檢查點確認內容品質。

## 1. 目錄結構

- `raw/`：原始參考資料摘要與出處紀錄（編號 `S1`–`S6`）。
- `wiki/`：整理後的知識條目：
  - `foundations/`：財務基石（緊急預備金、通膨、複利）
  - `instruments/`：指數與 ETF 原理（主被動比較、ETF 機制與費用、0050 vs. 全球 ETF）
  - `strategies/`：新手實作策略（資產配置、定期定額與再平衡）
  - `risk/`：風險與行為防線（波動 vs. 永久虧損、五大誤區、新手行動路線）
  - `sources/`：來源摘要頁（`source-S1` 至 `source-S6`）
- `index.md`：全站條目總目錄。

## 2. 條目 YAML Frontmatter 必填欄位

每篇 `wiki/` 條目頂端必須包含以下欄位：

```yaml
---
id: unique-kebab-case-id
title: 條目標題
category: foundations | instruments | strategies | risk | sources
summary: 一句話白話摘要
sources:
  - S1
updated: 2026-11-26
tags:
  - 關鍵字
---
```

## 3. 引用與檢查點規則

1. **行內來源引用**：凡涉及數據、法規或定義，必須在句末附上 `[S1]`–`[S6]` 引用標記，且該編號必須列於 frontmatter `sources` 中。
2. **雙向連結（Wikilinks）**：使用 `[[target-id]]` 連結至其他 `wiki/` 條目的 `id`，不可指向不存在的頁面。
3. **三道品質檢查點**：
   - **檢查點 1（`lint_wiki`）**：寫入 Wiki 後檢查 Frontmatter 欄位、有效來源編號、行內引用與零斷鏈。
   - **檢查點 2（`lint_outline`）**：產出簡報 HTML 前先檢查大綱 JSON 的事實依據（禁止未經證實的保證報酬宣稱）、引用覆蓋、單頁字數上限（≤ 220 字）與無未解釋專有名詞。
   - **檢查點 3（`lint_render`）**：建置靜態網頁後確認所有簡報連回 Wiki 的連結皆可解析，且互動元件完整載入。
