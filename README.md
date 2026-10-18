# Neiro-NQ-Quant: Cloud-First E-mini Nasdaq-100 Quant System

> **Hệ thống Định lượng & Phòng hộ Phái sinh E-mini Nasdaq-100 (CME: NQ / MNQ & CFD: US100)**  
> Kiến trúc Cloud-First: Tính toán trên GitHub Actions / Google Colab, lưu trữ trên Google Drive, hiển thị Zero-Waste trên MT5 & TradingView.

---

## 1. Mục tiêu cốt lõi (Core Objectives)

1. **Thu thập chuỗi Options Nasdaq (QQQ / NDX)** qua các nguồn API mở (yfinance, CBOE, Tradier).
2. **Giải mã ma trận vị thế Dealer (Dealer Positioning & GEX)**: Call Wall, Put Wall, Zero Gamma Flip, Synthetic ATM Pivot, 1-Sigma Expected Move.
3. **Phát hiện vùng chân không (OI Air Pockets)** và kích hoạt Gamma Squeeze.
4. **Kiến trúc Zero-Waste**: Toàn bộ dữ liệu thô (.parquet) đẩy lên Google Drive. Laptop cá nhân chỉ kéo đúng 1 file us100_levels.json (~2KB) về MT5 để vẽ lên chart, không tốn tài nguyên máy tính.

---

## 2. Cấu trúc thư mục (Project Structure)

`
Neiro-NQ-Quant/
├── .agents/skills/          -> Junction tới agent-skills
├── .github/workflows/       -> GitHub Actions (Cronjob tính toán tự động)
├── config/                  -> Cấu hình runtime (settings.toml)
├── docs/                    -> spec.md, architecture.md, database-schema.md
├── src/
│   ├── collector/           -> Thu thập options QQQ / NDX
│   ├── quant_engine/        -> GEX, Walls, Pivot, Expected Move
│   └── cloud_exporter/      -> Đồng bộ Drive & xuất JSON GitHub Raw
├── .gitignore
├── AGENTS.md / GEMINI.md    -> Bộ quy tắc cốt lõi cho AI Coding Agents
└── README.md
`

---

## 3. Quy định Zero-Waste & Lưu trữ đám mây

- **Local Machine (< 15MB):** Tuyệt đối không lưu trữ dữ liệu thô trên máy tính.
- **Google Drive (Cold Storage):** Lưu trữ toàn bộ snapshot lịch sử định dạng nén .parquet.
- **GitHub Raw (Hot Feed):** Cung cấp API công khai cho MT5 / TradingView.
