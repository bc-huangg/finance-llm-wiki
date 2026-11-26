# 個人理財與指數投資入門 — LLM Wiki 與教學型 HTML 簡報

以台灣大學生與社會新鮮人為目標讀者，整理「個人理財與指數投資入門」的知識庫（LLM Wiki），並以此為基礎製作 12 頁互動式教學 HTML 簡報。

## 線上瀏覽

- **LLM Wiki 知識庫**：https://bc-huangg.github.io/finance-llm-wiki/
- **教學型 HTML 簡報**：https://bc-huangg.github.io/finance-llm-wiki/slides.html

## 目錄結構

- `SCHEMA.md`：知識庫條目格式與檢查規則說明
- `raw/`：6 篇公開參考來源（`S1`–`S6`）
- `wiki/`：17 篇知識條目（11 篇概念條目 ＋ 6 篇來源摘要）
- `index.md`：全站條目總目錄
- `docs/`：靜態網頁成品（`index.html` 與 `slides.html`）
- `pipeline/`：簡報大綱、網頁建置腳本、分段檢查腳本與執行紀錄

## 執行檢查與建置

```powershell
python pipeline/run_graph.py --all
```
