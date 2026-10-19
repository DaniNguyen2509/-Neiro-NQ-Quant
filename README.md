# 📈 Neiro-NQ-Quant: Cloud-Native E-mini Nasdaq Quant Terminal

[![GitHub Actions CI/CD](https://github.com/DaniNguyen2509/-Neiro-NQ-Quant/actions/workflows/daily_options_sync.yml/badge.svg)](https://github.com/DaniNguyen2509/-Neiro-NQ-Quant/actions/workflows/daily_options_sync.yml)
[![GitHub Pages](https://img.shields.io/badge/GitHub%20Pages-Live%20Terminal-brightgreen)](https://daninguyen2509.github.io/-Neiro-NQ-Quant/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Zero-Waste](https://img.shields.io/badge/Zero--Waste-%3C15MB-success.svg)](README.md)

> **Hệ thống Định lượng Vi mô & Terminal Tác chiến E-mini Nasdaq-100 Futures (`NQ` / `MNQ` / `NAS100` / `US100` / `QQQ`)**  
> **Kiến trúc Cloud-Native 100% (Zero-Touch Automation):** Vận hành hoàn toàn tự động trên **GitHub Actions** theo **Lưới Cron Thích Ứng 2 Mùa**, giải mã ma trận Dealer theo mô hình **Black-76**, trực quan hóa **Plotly Dark Terminal HUD 3 Panels**, tự động xuất bản lên **GitHub Pages**.  
> ⚠️ **Thuần Python Đám mây:** Không cần bật laptop, **KHÔNG phụ thuộc MT5 hay TradingView**.

---

## ⚡ TRUY CẬP TRỰC TIẾP TERMINAL TRÊN WEB (LIVE GITHUB PAGES)

👉 **Bảng điều khiển Tác chiến:** [https://daninguyen2509.github.io/-Neiro-NQ-Quant/](https://daninguyen2509.github.io/-Neiro-NQ-Quant/)

Tự động cập nhật theo Lưới Cron Thích Ứng 2 Mùa (`cron: '30 0,7,8,12,13,14,15,16,17 * * 1-5'`):
1. **07:30 VN (00:30 UTC):** Chốt Open Interest từ CME Clearing.
2. **14:30 & 15:30 VN:** Đón đầu mở phiên London (mùa hè / mùa đông).
3. **19:30 - 00:30 VN:** Cập nhật mỗi 1 tiếng xuyên suốt phiên giao dịch Mỹ.

---

## 🚀 THỰC THI NHANH CỤC BỘ (LOCAL QUICKSTART)

```bash
# 1. Cài đặt thư viện:
pip install -r requirements.txt

# 2. Chạy bộ kiểm thử (14 tests pass 100%):
pytest tests/

# 3. Tạo Terminal Tác chiến Plotly Dark HUD ngay lập tức:
python -m src.hud.html_dashboard --source yfinance --basis 0.0

# 4. Tùy chỉnh độ lệch sàn MT5 (ví dụ Spot NAS100 lệch 15 điểm):
python -m src.hud.html_dashboard --basis 15.0

# File HTML kết quả tự động mở tại: exports/latest_nq_dashboard.html & exports/index.html
```

---

## 📚 TÀI LIỆU ĐẶC TẢ KIẾN TRÚC & DECISIONS

- **Đặc tả Kỹ thuật (Spec):** [docs/spec.md](docs/spec.md)
- **Kiến trúc Hệ thống (Architecture):** [docs/architecture.md](docs/architecture.md)
- **Đặc tả Schema Parquet & DuckDB:** [docs/database-schema.md](docs/database-schema.md)
- **Kiến trúc Quyết định (ADR):** [docs/decisions/ADR-001-cloud-native-options-quant-pipeline.md](docs/decisions/ADR-001-cloud-native-options-quant-pipeline.md)

---

## 📁 CẤU TRÚC KHO LƯU TRỮ (PROJECT STRUCTURE)

```
Neiro-NQ-Quant/
├── .github/workflows/
│   └── daily_options_sync.yml       # Lưới Cron Thích Ứng 2 Mùa & Deploy GitHub Pages
├── config/
│   └── settings.toml                # Cấu hình runtime & thông số định lượng
├── data/
│   └── options_prices_NQZ26.csv     # Snapshot options chain chuẩn mực
├── docs/
│   ├── spec.md                      # Đặc tả kỹ thuật cốt lõi (Source of Truth)
│   ├── architecture.md              # Kiến trúc hệ thống Cloud-Native & Data Flow
│   ├── database-schema.md           # Chuẩn schema Parquet, DuckDB tables
│   └── decisions/                   # Architecture Decision Records (ADRs)
├── exports/
│   ├── latest_nq_dashboard.html     # Tactical Terminal Plotly Dark Theme
│   ├── index.html                   # Web view trực tiếp cho GitHub Pages
│   └── nq_tactical_levels.json      # Bảng mốc chiến thuật JSON cho bot/indicator
├── src/
│   ├── collector/
│   │   ├── base.py                  # Base Collector interface
│   │   ├── greeks.py                # Black-Scholes Greeks legacy
│   │   ├── nasdaq_collector.py      # Bộ thu thập QQQ/NQ & Benchmark Generator
│   │   └── storage.py               # Quản lý Parquet & DuckDB
│   ├── quant_engine/
│   │   ├── black76.py               # Mô hình Black-76 cho Futures Options & IV Solver
│   │   ├── engine.py                # Lõi tính Net GEX, VEX, CHEX, Parity & Expected Move
│   │   ├── structure.py             # Cấu trúc vi mô & Microstructure levels
│   │   └── state_machine.py         # Level State Machine Engine
│   ├── hud/
│   │   └── html_dashboard.py        # Terminal Tác chiến Plotly Dark HUD & Anti-collision
│   ├── dashboard/
│   │   ├── html_dashboard.py        # Alias import tương thích ngược
│   │   └── visualizer.py            # Visualizer cổ điển
│   └── main.py                      # Pipeline entrypoint
├── tests/
│   ├── test_black76_and_terminal.py # Unit tests: Black-76, Greeks, Parity & Anti-collision
│   ├── test_collector.py            # Integration tests: Options collector & Dataframes
│   ├── test_greeks.py               # Unit tests: Greeks computation
│   ├── test_state_machine.py        # Unit tests: Level State Machine
│   └── test_visualizer.py           # Unit tests: Dashboard rendering
├── requirements.txt                 # Danh mục thư viện rút gọn (Loại bỏ Chromium bloat)
├── AGENTS.md / GEMINI.md            # Bộ quy tắc cốt lõi & Zero-Waste Mandate
└── README.md                        # Hướng dẫn nhanh & Giới thiệu hệ thống
```

---

## 🧹 QUY ĐỊNH ZERO-WASTE (< 15MB MANDATE)

- **Máy tính cá nhân (< 15MB):** Toàn bộ repository chỉ nặng **0.57 MB**. Tuyệt đối không tích tụ file rác, file `.pyc`, cache hay trình duyệt headless cồng kềnh.
- **Tự động dọn dẹp:** Mọi tác vụ scratch/test tạm thời đều được dọn dẹp sạch sẽ ngay sau khi thực thi.

