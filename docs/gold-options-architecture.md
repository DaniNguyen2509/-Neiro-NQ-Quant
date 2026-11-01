# Hướng dẫn Kiến trúc & Chuyển giao Sang Gold Options (XAUUSD / COMEX GC)

> **Tài liệu tham chiếu chuyển giao kỹ thuật (Adaptation & Porting Guide)**  
> **Từ:** Neiro-NQ-Quant (E-mini Nasdaq-100 Futures `NQ`)  
> **Sang:** Neiro-Gold-Quant (COMEX Gold Futures `GC` / Spot `XAUUSD` / ETF `GLD`)  
> **Mục tiêu:** Cung cấp tài liệu chuẩn hóa 100% về mặt toán học, cấu trúc dữ liệu, và quy đổi tham số để người dùng hoặc AI Agent kế thừa trực tiếp mã nguồn Neiro-NQ-Quant triển khai trọn vẹn cho thị trường Quyền chọn Vàng (Gold Options).

---

## 1. Bảng Đối Chiếu Thông Số Kỹ Thuật (NQ vs Gold GC)

Để chuyển đổi lõi định lượng từ Nasdaq sang Vàng, các hằng số và cấu hình cơ bản cần được điều chỉnh như sau:

| Hạng mục | Neiro-NQ-Quant (Hiện tại) | Neiro-Gold-Quant (Chuyển giao) | Ghi chú & Giải thích |
|---|---|---|---|
| **Tài sản Tương lai (Futures)** | **`NQ` / `NQ=F`** (E-mini Nasdaq-100) | **`GC` / `GC=F`** (COMEX Gold Futures) | Sàn COMEX thuộc tập đoàn CME Group. |
| **Mã HĐTL Micro** | **`MNQ`** | **`MGC`** (Micro Gold Futures) | Phù hợp tài khoản vốn nhỏ. |
| **Hệ số nhân (Multiplier)** | **$20.0** / điểm (`MNQ`: $2.0) | **$100.0** / điểm (`MGC`: $10.0) | 1 hợp đồng GC chuẩn đại diện cho 100 troy ounces vàng; MGC đại diện cho 10 oz. |
| **Mã TradingView liên tục** | `NQ1!` | `GC1!` | Mã hợp đồng tương lai liên tục (Continuous Front Month). |
| **Mã Sàn Quỹ / Spot CFD** | `NAS100` / `US100` / `USTEC` | **`XAUUSD`** / **`GOLD`** | Spot Gold London OTC neo qua tỷ giá USD. |
| **Proxy Options Thanh khoản** | **`QQQ`** (Invesco QQQ Trust) | **`GLD`** (SPDR Gold Shares) hoặc **`IAU`** | `GLD` là ETF vàng lớn nhất thế giới, có chuỗi Options thanh khoản cực cao và đáo hạn hàng tuần (Weekly Options). |
| **Tỷ lệ Ánh xạ Proxy (Basis Ratio)** | $NQ \approx 41.0 \times QQQ$ | $GC \approx 10.8 \times GLD$ | Ví dụ: Khi Vàng $GC = 2,700$, ETF $GLD \approx 250$ USD/cổ phiếu $\rightarrow$ Tỷ lệ ánh xạ $\approx 10.8$. |
| **Chỉ số Biến động (Volatility Index)** | **`VXN`** (CBOE Nasdaq Volatility) | **`GVZ`** (CBOE Gold Volatility Index) | `GVZ` đo lường biến động hàm ý kỳ hạn 30 ngày của quyền chọn vàng `GLD`. |
| **Chu kỳ Đáo hạn Chính (Rollover)** | 4 tháng Quý: **H, M, U, Z** (T3, T6, T9, T12) | 5 tháng chẵn: **G, J, M, Q, Z** (T2, T4, T6, T8, T12) | Tháng 12 (Z) và Tháng 6 (M) là hai kỳ hạn có thanh khoản vàng lớn nhất năm. |
| **Độ dốc Biến động (IV Skew)** | **Put Skew** (Quỹ mua Put bảo hiểm đè phòng hộ) | **Call Skew** (Nhu cầu mua Call phòng hộ đà tăng và rủi ro địa chính trị) | Trên thị trường vàng, Call OTM thường có IV cao hơn Put OTM (ngược lại với chứng khoán). |

---

## 2. Mô Hình Định Giá Cost of Carry cho Vàng

### 2.1. Công thức Giá Hợp đồng Tương lai Lý thuyết

Không giống như chỉ số chứng khoán (có tỷ suất cổ tức $d$), vàng vật chất chịu **chi phí lưu kho, kiểm định và bảo hiểm ($u$)**, đồng thời có thể sinh ra **lợi suất cho thuê vàng ($y$ - Gold Lease Rate)**:

$$F_{0, \text{lý thuyết}} = S_0 \times e^{(r + u - y)T}$$

Trong đó:
- $S_0$: Giá vàng giao ngay (Spot Gold London OTC / XAUUSD).
- $r$: Lãi suất phi rủi ro USD (SOFR hoặc Treasury Yield 3M $\approx 4.0 - 4.5\%$).
- $u$: Chi phí lưu kho và bảo hiểm vật chất tại kho COMEX ($\approx 0.15 - 0.25\%$/năm).
- $y$: Gold Lease Rate (Lợi suất cho thuê vàng giữa các Bullion Banks). Khi các ngân hàng trung ương gom vàng vật chất gấp, $y$ tăng mạnh làm kiềm chế giá Futures so với Spot.
- $T$: Thời gian còn lại đến ngày đáo hạn của hợp đồng tương lai tính theo năm.

### 2.2. Độ Lệch Basis & Cơ Chế EFP (Exchange for Physical)

$$\text{Basis} = F_{0, \text{thực tế}} - S_{0, \text{Spot}}$$

$$\text{Điểm vào lệnh trên MT5 (XAUUSD)} = \text{Strike } K_{(\text{Futures } GC)} - \text{Basis}$$

- **Ý nghĩa độ lệch $\Delta F = F_{0, \text{thực tế}} - F_{0, \text{lý thuyết}}$:**
  * **$\Delta F \gg 0$ (Futures đắt hơn lý thuyết):** Lực mua chủ động cực mạnh trên sàn COMEX New York. Thường kích hoạt nghiệp vụ EFP: Các ngân hàng bán khống GC Futures và mua gom vàng giao ngay London (XAUUSD), kéo giá Spot tăng đuổi theo.
  * **$\Delta F \ll 0$ (Futures rẻ hơn lý thuyết):** Áp lực xả hàng phòng hộ của các nhà sản xuất vàng, kéo giá vàng Spot sụt giảm thu hẹp khoảng cách.

---

## 3. Ứng Dụng Mô Hình Black-76 cho Gold Options

Mọi công thức toán học cốt lõi đã được kiểm chứng chuẩn xác trong Neiro-NQ-Quant đều áp dụng nguyên vẹn cho Gold Options:

### 3.1. Định Giá và Các Biến Trung Gian
$$d_1 = \frac{\ln(F/K) + \frac{1}{2}\sigma^2 T}{\sigma \sqrt{T}}, \quad d_2 = d_1 - \sigma \sqrt{T}$$

$$C = e^{-rT} \left[ F N(d_1) - K N(d_2) \right]$$
$$P = e^{-rT} \left[ K N(-d_2) - F N(-d_1) \right]$$

### 3.2. Bộ Greeks Giải tích Toàn diện
- **Delta ($\Delta$):** $\Delta_{\text{Call}} = e^{-rT} N(d_1), \quad \Delta_{\text{Put}} = -e^{-rT} N(-d_1)$
- **Gamma ($\Gamma$):** $\Gamma = e^{-rT} \frac{N'(d_1)}{F \sigma \sqrt{T}}$
- **Vega ($\nu$):** $\nu = e^{-rT} F \sqrt{T} N'(d_1)$
- **Vanna ($VEX$):** $\text{Vanna} = -e^{-rT} N'(d_1) \frac{d_2}{\sigma}$
- **Charm ($CHEX = -\partial \Delta / \partial T$):**
  $$\text{Charm}_{\text{Call}} = e^{-rT} \left[ r N(d_1) + N'(d_1) \frac{d_2}{2T} \right]$$
  $$\text{Charm}_{\text{Put}} = e^{-rT} \left[ -r N(-d_1) + N'(d_1) \frac{d_2}{2T} \right]$$

### 3.3. Dòng Tiền Dealer ($M) trên Vàng
Với hệ số nhân $Multiplier = 100$ (cho GC):
- **Net GEX ($M / 1% dịch chuyển giá vàng):**
  $$\text{Net GEX}_K = \left( OI_{\text{Call}, K} \times \Gamma_K - OI_{\text{Put}, K} \times \Gamma_K \right) \times 100 \times F_0^2 \times 0.01$$
- **Net VEX ($M / 1% IV):**
  $$\text{Net VEX}_K = \left( OI_{\text{Call}, K} \times \text{Vanna}_K - OI_{\text{Put}, K} \times \text{Vanna}_K \right) \times 100 \times F_0 \times 0.01$$
- **Net CHEX ($M / ngày):**
  $$\text{Net CHEX}_K = \left( OI_{\text{Call}, K} \times \text{Charm}_{\text{Call}, K} - OI_{\text{Put}, K} \times \text{Charm}_{\text{Put}, K} \right) \times 100 \times F_0 \times \frac{1}{365}$$

---

## 4. Các Bước Kế Thừa Mã Nguồn (Step-by-Step Porting)

Khi tạo repository mới (ví dụ: `Neiro-Gold-Quant`):

1. **Khởi tạo Collector cho Vàng (`src/collector/gold_collector.py`):**
   - Sử dụng `yfinance` quét mã `GLD` (SPDR Gold Trust Options) làm proxy chính, hoặc lấy trực tiếp mã HĐTL `GC=F`.
   - Tính hệ số quy đổi: $\text{Basis Ratio} = \text{Spot}_{GC} / \text{Spot}_{GLD}$.
   - Nhân toàn bộ Strike của `GLD` với Basis Ratio để ra Strike quy đổi sang Vàng Futures $GC.

2. **Cập nhật Tham Số trong `config/settings.toml`:**
   ```toml
   [symbol]
   primary = "GC"
   futures_symbol = "GC=F"
   proxy_symbol = "GLD"
   multiplier = 100.0          # 100 oz cho hợp đồng tiêu chuẩn GC (hoặc 10.0 cho MGC)
   default_step = 10.0         # Mức chia Strike phổ biến của Vàng (mỗi 10-25 USD)
   volatility_index = "^GVZ"   # CBOE Gold Volatility Index
   ```

3. **Cơ chế Kháng cự & Bẫy Thanh khoản trên Vàng:**
   - **Call Wall Vàng:** Thường rất dày do tâm lý mua tích trữ và phòng vệ lạm phát của các quỹ tài sản và nhà đầu tư cá nhân toàn cầu.
   - **Put Wall Vàng:** Điểm nâng đỡ giá sàn của các Bullion Banks và thợ đào vàng (Hedging sản lượng).
   - **Gamma Squeeze Vàng:** Khi nến M5 vượt qua $\text{Trigger}_{\text{Up}} = K_{\text{CallWall}} + C_{\text{mid}}$, đà tăng có thể kích hoạt chuỗi mua đuổi cực mạnh (Short Squeeze).

4. **Tái Sử Dụng Nguyên Vẹn Bộ Visualizer & Dual-View HUD:**
   - [`src/hud/html_dashboard.py`](file:///c:/Users/Daniel/Documents/My-Projects/Neiro-NQ-Quant/src/hud/html_dashboard.py) và thuật toán Chống đè chữ (Anti-Collision Layout) hoạt động độc lập với loại tài sản, chỉ cần truyền vào `--multiplier 100.0` và `--basis <độ_lệch_XAUUSD>`.
