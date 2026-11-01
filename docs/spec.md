# Spec: Neiro-NQ-Quant (Cloud-Native E-mini Nasdaq Quant Terminal)

> **Mục tiêu:** Hệ thống tự động thu thập chuỗi Options, phân tích vi mô dòng tiền Nhà tạo lập (Dealer GEX/DEX/VEX/CHEX theo mô hình Black-76 chuẩn xác cho Futures Options), tính toán Put-Call Parity Synthetic Pivot, phát hiện bẫy thanh khoản vi mô (Air Pockets, Structural Walls, Gamma Squeeze Triggers), và trực quan hóa Terminal Tác chiến Đa Chế Độ Dual-View (ATAS Orderflow Footprint Canvas + 3-Panel Plotly Quant Price Ladder & Tactical Playbook) cho E-mini Nasdaq-100 Futures (`NQ` / `MNQ` / `QQQ` / `NAS100` / `US100`).  
> **Kiến trúc vận hành:** **100% Cloud-Native Zero-Touch Automation** chạy hoàn toàn trên **GitHub Actions** với Lưới Cron Đa Tầng Pre-Session Radar & Dual-Stage Thích Ứng 2 Mùa (bao trọn nhịp 0DTE Power Hour), tự động xuất bản lên **GitHub Pages**, hoàn toàn không phụ thuộc máy tính cá nhân hay phần mềm bên ngoài (Không cần bật máy, Không MT5, Không TradingView).

---

## 1. Objective & Core Capabilities (Mục tiêu cốt lõi)

1. **Thu thập chuỗi Options Nasdaq tự động:**
   - Quét dữ liệu quyền chọn thực tế qua API Python mở (`yfinance` với QQQ làm proxy thanh khoản lớn nhất, 0DTE mỗi ngày) và bộ nạp chuẩn hóa (`src/collector/nasdaq_collector.py`).
   - Tốc độ siêu tốc (< 4 giây), vượt tường lửa Cloudflare 100%, không cần cài đặt Chromium cồng kềnh (tiết kiệm 300MB băng thông).
   - Cơ chế nạp dữ liệu offline/benchmark dự phòng khi ngoài giờ giao dịch (`generate_benchmark_nq_chain`).
   - **Xử lý NaN-Safe & Sạch dữ liệu (`clean_num`):** Loại bỏ hoàn toàn lỗi lan truyền `NaN` khi dữ liệu Volume, Open Interest hoặc IV bị khuyết từ nguồn sàn.
   - **Kỳ hạn DTE Động theo Múi Giờ New York (`America/New_York`):**
     * Trong các phiên giao dịch 0DTE, DTE được tính đếm ngược từng phút đến giờ đóng cửa 16:00 ET ($T_{\text{days}} = \max(0.01, \Delta t / 1440)$), phản ánh chân thực độ dốc suy tàn thời gian (Theta/Charm decay curve) trong giờ cao điểm Power Hour thay vì dùng số tĩnh.

2. **Lõi Định lượng Vi mô Black-76 (Quant Microstructure Engine):**
   - **Mô hình định giá Black-76** chuyên biệt cho Hợp đồng Tương lai (Futures Options) với hệ số chiết khấu $e^{-rT}$:
     $$d_1 = \frac{\ln(F/K) + \frac{1}{2}\sigma^2 T}{\sigma \sqrt{T}}, \quad d_2 = d_1 - \sigma \sqrt{T}$$
     $$C = e^{-rT} \left[ F N(d_1) - K N(d_2) \right]$$
     $$P = e^{-rT} \left[ K N(-d_2) - F N(-d_1) \right]$$
   - **Bộ Greeks Giải tích Toàn diện (1st & 2nd Order):**
     * **Delta ($\Delta$):**
       $$\Delta_{\text{Call}} = e^{-rT} N(d_1), \quad \Delta_{\text{Put}} = -e^{-rT} N(-d_1)$$
     * **Gamma ($\Gamma$):**
       $$\Gamma = e^{-rT} \frac{N'(d_1)}{F \sigma \sqrt{T}}$$
     * **Vega ($\nu$):**
       $$\nu = e^{-rT} F \sqrt{T} N'(d_1)$$
     * **Vanna ($VEX = \frac{\partial \Delta}{\partial \sigma}$):**
       $$\text{Vanna} = -e^{-rT} N'(d_1) \frac{d_2}{\sigma}$$
     * **Charm ($CHEX = -\frac{\partial \Delta}{\partial T}$):**
       $$\text{Charm}_{\text{Call}} = e^{-rT} \left[ r N(d_1) + N'(d_1) \frac{d_2}{2T} \right]$$
       $$\text{Charm}_{\text{Put}} = e^{-rT} \left[ -r N(-d_1) + N'(d_1) \frac{d_2}{2T} \right]$$
       *(Đã kiểm chứng khớp 100% với đạo hàm giải tích vi phân hữu hạn sai số $< 10^{-10}$).*
   - **Thuật toán giải ngược IV lai (Hybrid Newton-Raphson + Brent Bisection):** Hội tụ ổn định tuyệt đối sai số $< 10^{-4}$ cho cả quyền chọn 0DTE (gần hết hạn) và Deep OTM/ITM.
   - **Put-Call Parity Synthetic Pivot:**
     $$S_{\text{Implied}} = K_{\text{ATM}} + e^{rT}(C_{\text{ATM}} - P_{\text{ATM}})$$
   - **Quy đổi Đòn bẩy CME Futures:** Hỗ trợ linh hoạt Multiplier $20/điểm (E-mini NQ) và $2/điểm (Micro E-mini MNQ) qua tham số `--multiplier`. Net GEX tính theo triệu USD trên 1% dịch chuyển giá ($M/1%), Net VEX ($M/1% IV), Net CHEX ($M/ngày).
   - **Dải Biến động Kỳ vọng (Expected Move):**
     * Công thức Brenner-Subrahmanyam: $\text{EM}_{1\sigma} \approx \frac{S_{\text{ATM}}}{0.7979}$
     * Quy tắc Rule of 16 cho biến động kỳ vọng trong ngày: $\text{Daily EM} = \frac{\text{IV}_{\text{ATM}}}{\sqrt{252}} \times S$
   - **Hệ thống Cản Chiến thuật & Squeeze Triggers:**
     * Call Wall, Put Wall, Absolute Gamma Peak, Pin Risk Magnet.
     * **Gamma Squeeze Trigger (Phá trần ép mua):**
       $$\text{Trigger}_{\text{Up}} = K_{\text{CallWall}} + C_{\text{mid}}(K_{\text{CallWall}})$$
     * **Waterfall Trigger (Thủng sàn ép bán tháo):**
       $$\text{Trigger}_{\text{Down}} = K_{\text{PutWall}} - P_{\text{mid}}(K_{\text{PutWall}})$$
     * Vùng chân không thanh khoản (OI Air Pockets: $OI < 0.35 \times \text{Mean}(OI)$).

3. **Giao diện Tác chiến Đa Chế Độ Dual-View Terminal HUD:**
   - Hỗ trợ chuyển đổi mượt mà 2 chế độ tác chiến chuyên nghiệp ngay trên thanh điều khiển (Navigation Header):
     * **TAB 1: ATAS ORDERFLOW FOOTPRINT:** Bảng thang giá chuyên sâu phong cách ATAS/Sierra Chart vẽ trên Canvas HTML5 hiệu năng cao (60 FPS). Hiển thị Volume Profile, Bid/Ask Footprint Delta, nến micro và bảng khớp lệnh Tick-by-Tick.
     * **TAB 2: 3-PANEL QUANT LADDER & TACTICAL PLAYBOOK:** Bố cục 3 Panels thang giá ngang Plotly tương tác:
       - **Panel 1:** Net GEX Profile ($M) & Mốc Chiến thuật Dynamic (kèm SL/TP tự động).
       - **Panel 2:** Dòng tiền Khối lượng (Volume) vs Open Interest nén (OI Concentration).
       - **Panel 3:** Greeks bậc 2 tương tác (Vanna & Charm Flow).
       - **Bảng Intraday Scalping Strategy:** Kịch bản lướt sóng nhanh trong ngày (30-50 điểm NQ).
       - **Bảng Structural Swing Walls:** Mốc thành trì phục kích sóng trung hạn.
       - **Bảng Strike Microstructure Matrix:** Phân tích chi tiết từng Strike (Call/Put OI, Volume, Greeks, Air Pocket flag).
   - **Thuật toán Chống Đè Chữ (Anti-Collision Algorithm):**
     * Legend đưa ra ngoài đồ thị ($y = 1.07$, hướng ngang).
     * Mốc Spot CME Futures neo sát mép phải ($x = 0.98$, $y_{\text{ref}} = \text{paper}$).
     * Tự động tạo khoảng cách giãn dòng dọc nếu đỉnh Vanna và Charm nằm trùng một mức Strike.
   - **Đồng bộ Sàn Spot MT5 qua Basis Offset:** Hỗ trợ tham số `--basis` ($Spot_{\text{MT5}} = Spot_{\text{Futures}} - \text{Basis}$).

4. **Tự động hóa Zero-Touch (GitHub Actions & Pages):**
   - **Lưới Cron Đa Tầng Pre-Session Radar & Dual-Stage Thích Ứng 2 Mùa:**
     * **07:15 VN (`15 0 * * 1-5`):** Chốt Open Interest chính thức từ CME Clearing (cố định Call/Put Wall khung ngày).
     * **Phiên Âu 2 nấc (`30 5,6,7,8 * * 1-5`):** 12:30 & 13:30 VN (Pre-Europe hè & đông trước Frankfurt/London) + 14:30 & 15:30 VN (In-Session hè & đông sau mở London 30 phút).
     * **Phiên Mỹ Full-Coverage (`45 11,12,13,14,15,16,17,18,19 * * 1-5`):** 18:45 VN (đón đầu tin vĩ mô CPI/NFP) $\rightarrow$ 19:45, 20:45, 21:45, 22:45, 23:45, 00:45, 01:45 VN (xuyên suốt mở cửa NYSE & London Fix) $\rightarrow$ **02:45 VN (Radar đón đầu 0DTE Power Hour & Market Close)**.
   - Tự động xuất bản Terminal lên **GitHub Pages** (`gh-pages`) và xuất feed `exports/nq_tactical_levels.json` cho Trading Bot / Telegram / EA.

---

## 2. Tech Stack

- **Ngôn ngữ:** Python 3.10+ (tương thích Python 3.12 trên GitHub runner & Python 3.14).
- **Thu thập dữ liệu:** `yfinance`, `requests`.
- **Lõi toán & Định lượng:** `numpy`, `pandas`, `scipy` (Black-76, Brent solver, Parity).
- **Trực quan hóa Terminal:** `plotly`, Canvas HTML5 Dark Theme, Vanilla JavaScript.
- **Cơ sở dữ liệu Đám mây:** `pyarrow`, `duckdb` (Serverless Parquet).
- **Tự động hóa CI/CD:** GitHub Actions (Lưới Cron Đa Tầng Pre-Session Radar & Dual-Stage) + GitHub Pages.
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

# 4. Chạy cho tài khoản Micro E-mini MNQ ($2/điểm) và độ lệch sàn MT5 15 điểm:
python -m src.hud.html_dashboard --source yfinance --multiplier 2.0 --basis 15.0

# 5. Chạy Pipeline tổng hợp:
python -m src.main --basis 0.0
```

---

## 4. Project Structure (Cấu trúc thư mục)

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
│   ├── database-schema.md           # Chuẩn schema Parquet, DuckDB tables & Tactical JSON
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

---

## 5. Testing & Quality Standards

1. **Unit Tests Black-76 & Greeks (`tests/test_black76_and_terminal.py` & `tests/test_greeks.py`):**
   - Kiểm tra Put-Call Parity của Black-76: $C - P = e^{-rT}(F - K)$.
   - Kiểm tra bộ giải ngược IV lai (Newton-Brent) hội tụ chính xác với sai số $< 10^{-4}$.
   - **Kiểm định Giải tích Vi phân Charm (Finite Difference Test):** Đạo hàm giải tích Charm ($\text{CHEX} = -\partial \Delta / \partial T$) được đối chiếu trực tiếp với đạo hàm số bậc hữu hạn ($h = 10^{-6}$), khớp chính xác với sai số $< 10^{-10}$.
   - Kiểm tra tính toán Net GEX, Net VEX, Net CHEX và Synthetic Pivot.
   - Kiểm tra thuật toán chống đè chữ (Anti-Collision) trên Plotly Layout.
2. **Standard Tests (`tests/`):**
   - Toàn bộ **14/14 tests** đạt trạng thái PASS 100%.
   - Dung lượng mã nguồn và tài nguyên được kiểm soát nghiêm ngặt $< 15MB$ theo Zero-Waste Mandate.
