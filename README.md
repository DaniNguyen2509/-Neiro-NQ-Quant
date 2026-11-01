# 📈 Neiro-NQ-Quant: Cloud-Native E-mini Nasdaq Quant Terminal

[![GitHub Actions CI/CD](https://github.com/DaniNguyen2509/-Neiro-NQ-Quant/actions/workflows/daily_options_sync.yml/badge.svg)](https://github.com/DaniNguyen2509/-Neiro-NQ-Quant/actions/workflows/daily_options_sync.yml)
[![GitHub Pages](https://img.shields.io/badge/GitHub%20Pages-Live%20Terminal-brightgreen)](https://daninguyen2509.github.io/-Neiro-NQ-Quant/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Zero-Waste](https://img.shields.io/badge/Zero--Waste-%3C15MB-success.svg)](README.md)
[![Tests Status](https://img.shields.io/badge/Tests-14%2F14%20PASS-brightgreen.svg)](tests/)

> **Hệ thống Định lượng Vi mô & Terminal Tác chiến E-mini Nasdaq-100 Futures (`NQ` / `MNQ` / `NAS100` / `US100` / `QQQ`)**  
> **Kiến trúc Cloud-Native 100% (Zero-Touch Automation):** Vận hành hoàn toàn tự động trên **GitHub Actions** theo **Lưới Cron Đa Tầng Pre-Session Radar & Dual-Stage Thích Ứng 2 Mùa**, giải mã ma trận Dealer theo mô hình **Black-76** (Greeks giải tích bậc 1 & bậc 2: Delta, Gamma, Vega, Vanna, Charm), trực quan hóa **Terminal Đa Chế Độ Dual-View** (ATAS Orderflow Footprint Canvas + 3-Panel Plotly Quant Price Ladder & Tactical Playbook), tự động xuất bản lên **GitHub Pages**.  
> ⚠️ **Thuần Python Đám mây:** Không cần bật laptop, **KHÔNG phụ thuộc MT5 hay TradingView**.

---

## ⚡ TRUY CẬP TRỰC TIẾP TERMINAL TRÊN WEB (LIVE GITHUB PAGES)

👉 **Bảng điều khiển Tác chiến Live:** [https://daninguyen2509.github.io/-Neiro-NQ-Quant/](https://daninguyen2509.github.io/-Neiro-NQ-Quant/)

Giao diện tích hợp bộ chuyển đổi tab linh hoạt:
- **TAB 1: ATAS ORDERFLOW:** Sổ lệnh thang giá dọc, Bid/Ask Footprint Delta, Micro-candles và Tape khớp lệnh 60 FPS phong cách ATAS / Sierra Chart.
- **TAB 2: 3-PANEL QUANT LADDER:** Đồ thị Plotly 3-Panel tương tác (Net GEX Profile, OI Concentration, 2nd Order Greeks Flow), KPI Cards, Bảng Kịch bản Chiến thuật Intraday Scalping Strategy và Bảng Structural Swing Walls.

Tự động cập nhật theo **Lưới Cron Đa Tầng Pre-Session Radar & Dual-Stage 0DTE** (14 lần/ngày):
1. **07:15 VN (`15 0 * * 1-5`):** Chốt Open Interest chính thức từ CME Clearing (cố định Call/Put Wall khung ngày).
2. **Phiên Âu 2 nấc (`30 5,6,7,8 * * 1-5`):** Pre-Europe (12:30 hè / 13:30 đông) & In-Session sau mở cửa London 30p (14:30 hè / 15:30 đông).
3. **Phiên Mỹ Full-Coverage (`45 11,12,13,14,15,16,17,18,19 * * 1-5`):** Đón đầu tin vĩ mô CPI/NFP (18:45 VN), bao trọn giờ mở cửa NYSE (19:45 - 21:45 VN), London Fix (23:45 VN), và **0DTE Power Hour Radar (02:45 VN)** trước giờ đóng cửa sàn New York.

---

## 🚀 THỰC THI NHANH CỤC BỘ (LOCAL QUICKSTART)

```bash
# 1. Cài đặt thư viện:
pip install -r requirements.txt

# 2. Chạy bộ kiểm thử (14/14 tests pass 100%):
pytest tests/

# 3. Tạo Terminal Tác chiến Dual-View qua Live Engine yfinance:
python -m src.hud.html_dashboard --source yfinance --basis 0.0

# 4. Chạy cho tài khoản Micro E-mini MNQ ($2/điểm) và độ lệch sàn MT5 15 điểm:
python -m src.hud.html_dashboard --source yfinance --multiplier 2.0 --basis 15.0

# 5. Chạy Pipeline tổng hợp:
python -m src.main --basis 0.0

# File HTML kết quả tự động mở tại: exports/latest_nq_dashboard.html & exports/index.html
# Feed JSON cho Bot/EA: exports/nq_tactical_levels.json
```

---

## 📚 TÀI LIỆU ĐẶC TẢ KIẾN TRÚC & DECISIONS

- **Đặc tả Kỹ thuật (Spec):** [docs/spec.md](docs/spec.md)
- **Kiến trúc Hệ thống (Architecture):** [docs/architecture.md](docs/architecture.md)
- **Đặc tả Schema Parquet, DuckDB & JSON Feed:** [docs/database-schema.md](docs/database-schema.md)
- **Hướng dẫn Chuyển giao sang Gold Options (XAUUSD / GC):** [docs/gold-options-architecture.md](docs/gold-options-architecture.md)
- **Kiến trúc Quyết định (ADR):**
  - [ADR-001: Cloud-Native Options Quant Pipeline](docs/decisions/ADR-001-cloud-native-options-quant-pipeline.md)
  - [ADR-002: Dual-View Terminal HUD & Black-76 Microstructure](docs/decisions/ADR-002-dual-view-terminal-and-black76-microstructure.md)

---

## 📁 CẤU TRÚC KHO LƯU TRỮ (PROJECT STRUCTURE)

```
Neiro-NQ-Quant/
├── .github/workflows/
│   └── daily_options_sync.yml       # Lưới Cron Đa Tầng Pre-Session Radar & Deploy GitHub Pages
├── config/
│   └── settings.toml                # Cấu hình runtime & thông số định lượng
├── data/
│   └── options_prices_NQZ26.csv     # Snapshot options chain chuẩn mực
├── docs/
│   ├── spec.md                      # Đặc tả kỹ thuật cốt lõi (Source of Truth)
│   ├── architecture.md              # Kiến trúc hệ thống Cloud-Native & Data Flow
│   ├── database-schema.md           # Chuẩn schema Parquet, DuckDB & JSON Feed
│   ├── gold-options-architecture.md # Hướng dẫn kiến trúc & chuyển giao sang Gold Options (XAUUSD/GC)
│   └── decisions/                   # Architecture Decision Records (ADRs)
│       ├── ADR-001-cloud-native-options-quant-pipeline.md
│       └── ADR-002-dual-view-terminal-and-black76-microstructure.md
├── exports/
│   ├── latest_nq_dashboard.html     # Tactical Terminal Dual-View (ATAS + Plotly 3-Panel)
│   ├── index.html                   # Web view trực tiếp cho GitHub Pages
│   └── nq_tactical_levels.json      # Bảng mốc chiến thuật & recommendations JSON
├── src/
│   ├── collector/
│   │   ├── base.py                  # Base Collector interface
│   │   ├── greeks.py                # Black-Scholes Greeks chuẩn hóa
│   │   ├── nasdaq_collector.py      # Bộ thu thập QQQ/NQ, Dynamic DTE & Benchmark Generator
│   │   └── storage.py               # Quản lý Parquet & DuckDB
│   ├── quant_engine/
│   │   ├── black76.py               # Mô hình Black-76 chuẩn xác (Delta, Gamma, Vega, Vanna, Charm)
│   │   ├── engine.py                # Lõi tính Net GEX/VEX/CHEX, Squeeze Triggers & Parity
│   │   ├── structure.py             # Cấu trúc vi mô & Microstructure levels
│   │   └── state_machine.py         # Level State Machine Engine & SL/TP Reversal
│   ├── hud/
│   │   └── html_dashboard.py        # Terminal Dual-View (ATAS Footprint + Plotly 3-Panel HUD)
│   ├── dashboard/
│   │   ├── html_dashboard.py        # Alias import tương thích ngược
│   │   └── visualizer.py            # Visualizer cổ điển
│   └── main.py                      # Pipeline entrypoint
├── tests/
│   ├── test_black76_and_terminal.py # Unit tests: Black-76, Charm derivative, Parity & Anti-collision
│   ├── test_collector.py            # Integration tests: Options collector & Dataframes
│   ├── test_greeks.py               # Unit tests: Greeks computation & Charm finite difference
│   ├── test_state_machine.py        # Unit tests: Level State Machine
│   └── test_visualizer.py           # Unit tests: Dashboard rendering
├── requirements.txt                 # Danh mục thư viện rút gọn (Loại bỏ Chromium bloat)
├── AGENTS.md / GEMINI.md            # Bộ quy tắc cốt lõi & Zero-Waste Mandate
└── README.md                        # Hướng dẫn nhanh & Giới thiệu hệ thống
```
