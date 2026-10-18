# Spec: Neiro-NQ-Quant (Cloud-First E-mini Nasdaq Quant Terminal)

> **Mục tiêu:** Hệ thống tự động thu thập chuỗi Options, phân tích dòng tiền Nhà tạo lập (Dealer GEX/DEX/VEX/CHEX), phát hiện bẫy thanh khoản (Air Pockets), giám sát Level State Machine và trực quan hóa Dashboard tương tác đa tầng trên Google Colab cho E-mini Nasdaq-100 (`NQ` / `MNQ` / `QQQ` / `NDX`).  
> **Môi trường vận hành cốt lõi:** 100% Python chạy trên **Google Colab (1-Click Run)** kết hợp tự động hóa **GitHub Actions**, lưu trữ đám mây Google Drive (Parquet Zero-Waste), **KHÔNG phụ thuộc phần mềm bên ngoài (Không MT5, Không TradingView)**.

---

## 1. Objective (Mục tiêu cốt lõi)

1. **Thu thập chuỗi Options Nasdaq tự động:**
   - Trực tiếp quét chuỗi quyền chọn của `QQQ` (Invesco QQQ Trust - proxy thanh khoản lớn nhất với 0DTE mỗi ngày) và `NDX` (Nasdaq-100 Index) qua API Python mở (`yfinance`, CBOE delayed).
   - Cơ chế **Dual-Frame**: Thu thập song song cả kỳ hạn ngắn hạn (0DTE/Weekly - áp lực Gamma scalping) và kỳ hạn dài hạn (Monthly/Quarterly - vị thế bảo hiểm của tổ chức).
2. **Lõi Định lượng Vi mô (Quant Microstructure Engine):**
   - Mô hình định giá Black-Scholes / Black-76 kết hợp IV Solver bisection.
   - Xác định bộ Greeks bậc 1 và bậc 2: Delta ($\Delta$), Gamma ($\Gamma$), Vega ($\nu$), Vanna ($VEX$), Charm ($CHEX$).
   - Ma trận Vị thế Dealer: Net Gamma Exposure (GEX Profile), Delta Exposure (DEX Flow), Điểm cân bằng Implied ATM Pivot, Dải biến động kỳ vọng ($\pm 1\sigma, \pm 2\sigma$ Expected Move Bands với hệ số 0.85 cho 0DTE).
   - Bẫy thanh khoản vi mô: Call Wall, Put Wall, Pin Risk Magnet (Hố đen ghim giá), Absolute Gamma Strike, và Vùng chân không thanh khoản (OI Air Pockets $< 35\%$ trung bình).
3. **Cơ chế Giám sát Trạng thái (Level State Machine Engine):**
   - Theo dõi thời gian thực 4 trạng thái: `DORMANT`, `TRIGGERED_TESTING`, `ABSORPTION_DEFENDED` (Fade Reversal), `SLICED_VACUUM` (Breakout Runner).
4. **Kiến trúc Database Đám mây (Cloud Database):**
   - **Lưu trữ vĩnh cửu (Cold Storage):** Tự động đồng bộ lên Google Drive (`/content/drive/MyDrive/Neiro-NQ-Quant/data/`) dưới định dạng nén tối ưu `.parquet` (Snappy compression $< 20KB$/snapshot).
   - **Truy vấn phân tích (Analytical Engine):** Tích hợp DuckDB Serverless chạy trực tiếp trên file Parquet trong RAM Google Colab mà không tốn chi phí máy chủ hay dung lượng máy cá nhân (< 15MB).
5. **Bảng điều khiển Tác chiến (Interactive Dashboard):**
   - Trực quan hóa Plotly ATAS Dark Theme tương tác đa tầng (Zoom, Pan, Tooltip chi tiết từng Strike).
   - Xuất Kế hoạch giao dịch sắc bén (SL, TP, Kịch bản Breakout vs Fade Reversal) tích hợp DeepSeek AI Briefing.

---

## 2. Tech Stack

- **Ngôn ngữ:** Python 3.10+ (tương thích Google Colab & Python 3.14).
- **Thu thập dữ liệu:** `yfinance`, `httpx`, `requests`.
- **Xử lý số liệu & Ma trận:** `numpy`, `pandas`, `scipy`, `pyarrow`.
- **Cơ sở dữ liệu Đám mây:** Google Drive (Storage) + `DuckDB` (Serverless Embedded Querying) + Apache `Parquet`.
- **Tự động hóa CI/CD:** GitHub Actions (Cronjob tự động trước các phiên Á, Âu, Mỹ).
- **Trực quan hóa Dashboard:** `plotly` (HTML tương tác & Google Colab inline widget).
- **Cấu hình & Quản lý:** `tomli` / `toml` (đọc `settings.toml`).
- **Kiểm thử tự động:** `pytest`.

---

## 3. Commands (Lệnh thực thi chuẩn)

```bash
# 1. Cài đặt môi trường kiểm thử cục bộ (Local Development)
pip install -r requirements.txt

# 2. Chạy bộ kiểm thử tự động (Unit & Integration Tests)
pytest -v tests/

# 3. Chạy Pipeline định lượng (chế độ tiêu chuẩn):
python -m src.main --export-html

# 4. Chạy Pipeline định lượng (chế độ Dual-Frame: 0DTE + Monthly):
python -m src.main --dual-frame --export-html

# 5. Trên Google Colab (1-Click Run):
# Mở notebooks/Neiro_NQ_Quant.ipynb và bấm Ctrl + F9
```

---

## 4. Project Structure (Cấu trúc thư mục)

```
Neiro-NQ-Quant/
├── .agents/skills/              # Agent skills
├── .github/workflows/
│   └── daily_nasdaq_quant.yml   # Cronjob tự động hóa chạy trước các phiên
├── config/
│   └── settings.toml            # Cấu hình tham số ticker, quant, database & dashboard
├── docs/
│   ├── spec.md                  # Bản đặc tả kỹ thuật này (Source of Truth)
│   ├── architecture.md          # Chi tiết kiến trúc Cloud Database & Data Pipeline
│   └── database-schema.md       # Chuẩn schema Parquet, DuckDB tables & Hot JSON
├── notebooks/
│   └── Neiro_NQ_Quant.ipynb     # Google Colab Notebook All-In-One (1-Click Run)
├── src/
│   ├── collector/               # Thu thập Options QQQ/NDX & lưu trữ Parquet
│   │   ├── base.py              # Interface chuẩn cho mọi Data Collector
│   │   ├── greeks.py            # Vectorized Black-Scholes / Black-76 & IV Solver
│   │   ├── nasdaq_collector.py  # Thu thập QQQ/NDX Options, Dual-Frame & Greeks
│   │   └── storage.py           # Quản lý Parquet partition & DuckDB
│   ├── quant_engine/            # Lõi tính toán GEX, Walls, ATM Pivot, Air Pockets
│   │   ├── structure.py         # Call/Put Wall, ATM Pivot, Sigma Bands, Air Pockets
│   │   └── state_machine.py     # Level State Machine Engine & Trade Setups
│   ├── dashboard/               # Giao diện trực quan hóa tương tác
│   │   └── visualizer.py        # Plotly ATAS Dark Dashboard & AI Briefing
│   └── main.py                  # Entry point chạy pipeline end-to-end
├── tests/
│   ├── test_collector.py        # Integration test: Collector, Dual-frame, Parquet
│   ├── test_greeks.py           # Unit test: Greeks Delta, Gamma, Vanna, Charm, IV
│   └── test_state_machine.py    # Unit test: State Machine transitions & rules
├── requirements.txt             # Danh mục thư viện Python
├── AGENTS.md / GEMINI.md        # Bộ quy tắc cốt lõi
└── README.md                    # Hướng dẫn khởi động nhanh
```

---

## 5. Testing & Quality Strategy

1. **Unit Tests (`tests/test_greeks.py`):**
   - Kiểm tra tính toán Call/Put Delta, Gamma, Vega, Vanna, Charm.
   - Kiểm tra Put-Call Parity và ATM Pivot calculation.
   - Kiểm tra thuật toán giải ngược IV (`estimate_iv_brent`).
2. **State Machine Tests (`tests/test_state_machine.py`):**
   - Kiểm tra phân loại chính xác các trạng thái `DORMANT`, `TRIGGERED_TESTING`, `ABSORPTION_DEFENDED`, `SLICED_VACUUM`.
   - Kiểm tra tính toán Stop Loss và Take Profit theo cản.
3. **Integration Tests (`tests/test_collector.py`):**
   - Kiểm thử nạp chuỗi đơn và chuỗi Dual-Frame (`fetch_dual_frame_chains`).
   - Kiểm tra khả năng tạo, đọc, và cơ chế tự dọn dẹp Parquet Zero-Waste (`cleanup_old_local_cache`).
