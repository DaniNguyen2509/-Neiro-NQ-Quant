# Spec: Neiro-NQ-Quant (Cloud-Native E-mini Nasdaq Quant Terminal)

> **Mục tiêu:** Hệ thống tự động thu thập chuỗi Options, phân tích vi mô dòng tiền Nhà tạo lập (Dealer GEX/DEX/VEX/CHEX theo mô hình Black-76), tính toán Put-Call Parity Synthetic Pivot, phát hiện bẫy thanh khoản vi mô (Air Pockets, Structural Walls), và trực quan hóa Terminal tác chiến tương tác Plotly Dark HUD cho E-mini Nasdaq-100 Futures (`NQ` / `MNQ` / `QQQ` / `NAS100` / `US100`).  
> **Kiến trúc vận hành:** **100% Cloud-Native Zero-Touch Automation** chạy hoàn toàn trên **GitHub Actions** với Lưới Cron Thích Ứng 2 Mùa (Dual-Season Cron Grid), tự động xuất bản lên **GitHub Pages**, hoàn toàn không phụ thuộc máy tính cá nhân hay phần mềm bên ngoài (Không cần bật máy, Không MT5, Không TradingView).

---

## 1. Objective (Mục tiêu cốt lõi)

1. **Thu thập chuỗi Options Nasdaq tự động:**
   - Quét dữ liệu quyền chọn thực tế qua API Python mở (`yfinance` với QQQ làm proxy chuẩn thanh khoản lớn nhất, 0DTE mỗi ngày) và bộ nạp chuẩn hóa (`src/collector/nasdaq_collector.py`).
   - Tốc độ siêu tốc (< 4 giây), vượt tường lửa Cloudflare 100%, không cần cài đặt Chromium cồng kềnh (tiết kiệm 300MB băng thông).
   - Cơ chế nạp dữ liệu offline/benchmark dự phòng khi ngoài giờ giao dịch (`generate_benchmark_nq_chain`).
2. **Lõi Định lượng Vi mô Black-76 (Quant Microstructure Engine):**
   - Mô hình định giá **Black-76** chuyên biệt cho Hợp đồng Tương lai (Futures Options) với hệ số chiết khấu $e^{-rT}$.
   - Bộ Greeks đầy đủ bậc 1 và bậc 2: Delta ($\Delta$), Gamma ($\Gamma$), Vega ($\nu$), Vanna ($VEX$), Charm ($CHEX$).
   - Thuật toán giải ngược IV lai (Hybrid Newton-Raphson + Brent Bisection) ổn định tuyệt đối cho cả quyền chọn 0DTE (gần hết hạn) và Deep OTM/ITM.
   - **Put-Call Parity Synthetic Pivot:**
     $$S_{\text{Implied}} = K_{\text{ATM}} + e^{rT}(C_{\text{ATM}} - P_{\text{ATM}})$$
   - **Quy đổi Đòn bẩy CME Futures:** Multiplier = 20 ($20/điểm cho E-mini NQ), Net GEX tính theo triệu USD trên 1% dịch chuyển giá ($M/1%), Net VEX ($M/1% IV), Net CHEX ($M/ngày).
   - **Dải Biến động Kỳ vọng (Expected Move):**
     - Công thức Brenner-Subrahmanyam: $\text{EM}_{1\sigma} \approx \frac{S_{\text{ATM}}}{0.7979}$
     - Quy tắc Rule of 16 cho biến động kỳ vọng trong ngày: $\text{Daily EM} = \frac{\text{IV}_{\text{ATM}}}{\sqrt{252}} \times S$
   - **Hệ thống Cản Chiến thuật:** Call Wall, Put Wall, Absolute Gamma Peak, Vanna/Charm Inflection Strikes, và Vùng chân không thanh khoản (OI Air Pockets).
3. **Bảng điều khiển Tác chiến Plotly Dark Terminal HUD:**
   - Layout 3 Panels thang giá nằm ngang (Horizontal Price Ladder):
     * **Panel 1:** Net GEX Profile ($M) & Mốc Chiến thuật (SL/TP dynamic)
     * **Panel 2:** Dòng tiền Khối lượng (Volume) vs Open Interest nén (OI Concentration)
     * **Panel 3:** Greeks bậc 2 tương tác (Vanna & Charm Flow)
   - **Thuật toán Chống Đè Chữ (Anti-Collision Algorithm):**
     * Legend đưa ra ngoài đồ thị ($y = 1.07$, hướng ngang).
     * Mốc Spot CME Futures neo sát mép phải ($x = 0.98$, $y_{\text{ref}} = \text{paper}$).
     * Tự động tạo khoảng cách giãn dòng dọc nếu đỉnh Vanna và Charm nằm trùng một mức Strike.
   - **2 Bảng Chiến thuật Hành động:**
     * *Intraday Scalping Strategy:* Tác chiến lướt sóng nhanh trong ngày (ăn 30-50 điểm NQ).
     * *Structural Swing Walls:* Phục kích các thành trì quyền chọn lớn đánh sóng trung hạn.
   - **Đồng bộ Spot MT5 qua Basis Offset:** Hỗ trợ tham số `--basis` ($Spot_{\text{MT5}} = Spot_{\text{Futures}} - \text{Basis}$).
4. **Tự động hóa Zero-Touch (GitHub Actions & Pages):**
   - Lưới Cron Thích Ứng 2 Mùa (`cron: '30 0,7,8,12,13,14,15,16,17 * * 1-5'`):
     * 07:30 VN (00:30 UTC): Chốt số liệu Open Interest chính thức từ CME Clearing.
     * 14:30 & 15:30 VN: Đón đầu mở phiên London (mùa hè và mùa đông).
     * 19:30 - 00:30 VN: Cập nhật mỗi 1 tiếng xuyên suốt phiên Mỹ.
   - Tự động xuất bản Terminal lên **GitHub Pages** (`gh-pages`).

---

## 2. Tech Stack

- **Ngôn ngữ:** Python 3.10+ (tương thích Python 3.12 trên GitHub runner & Python 3.14).
- **Thu thập dữ liệu:** `yfinance`, `requests`.
- **Lõi toán & Định lượng:** `numpy`, `pandas`, `scipy` (Black-76, Brent solver, Parity).
- **Trực quan hóa Terminal:** `plotly` (HTML độc lập, responsive, dark ATAS theme).
- **Cơ sở dữ liệu Đám mây:** `pyarrow`, `duckdb` (Serverless Parquet).
- **Tự động hóa CI/CD:** GitHub Actions (Dual-Season Cron Grid) + GitHub Pages.
- **Kiểm thử tự động:** `pytest`.

---

## 3. Commands (Lệnh thực thi chuẩn)

```bash
# 1. Cài đặt thư viện:
pip install -r requirements.txt

# 2. Chạy toàn bộ 14 test kiểm thử (Pass 100%):
pytest tests/

# 3. Chạy Terminal Tác chiến Plotly qua Live Engine yfinance:
python -m src.hud.html_dashboard --source yfinance --basis 0.0

# 4. Chạy với độ lệch sàn MT5 (ví dụ Broker NAS100 lệch 15 điểm so với Futures NQ):
python -m src.hud.html_dashboard --basis 15.0

# 5. Chạy Pipeline tổng hợp:
python -m src.main --basis 0.0
```

---

## 4. Project Structure (Cấu trúc thư mục)

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
│   └── database-schema.md           # Chuẩn schema Parquet, DuckDB tables
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

## 5. Testing & Quality Standards

1. **Unit Tests Black-76 (`tests/test_black76_and_terminal.py`):**
   - Kiểm tra Put-Call Parity của Black-76: $C - P = e^{-rT}(F - K)$.
   - Kiểm tra bộ giải ngược IV lai (Newton-Brent) hội tụ chính xác với sai số $< 10^{-4}$.
   - Kiểm tra tính toán Net GEX, Net VEX, Net CHEX và Synthetic Pivot.
   - Kiểm tra thuật toán chống đè chữ (Anti-Collision) trên Plotly Layout.
2. **Standard Tests (`tests/`):**
   - Toàn bộ **14/14 tests** đạt trạng thái PASS 100%.
   - Dung lượng mã nguồn và tài nguyên được kiểm soát nghiêm ngặt $< 15MB$ theo Zero-Waste Mandate.
