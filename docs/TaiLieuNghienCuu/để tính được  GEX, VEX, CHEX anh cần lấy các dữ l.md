Để tính toán trọn vẹn bộ 3 chỉ số **GEX (Gamma Exposure)**, **VEX (Vanna Exposure)** và **CHEX (Charm Exposure)** cho chỉ số **E-mini Nasdaq-100 Futures (NQ)** như hệ thống 3 Panel anh đã xây dựng cho Vàng (GC), anh chỉ cần thu thập **6 biến số đầu vào cơ bản**.  
Về vấn đề dữ liệu **Miễn phí và Real-time (Thời gian thực)**: Câu trả lời là **CÓ (Miễn phí Real-time cho Giá, Volume và IV)**, nhưng anh cần nắm rõ một quy luật bất biến của toàn bộ thị trường tài chính Phố Wall về dữ liệu **Open Interest (OI)**.  
**1\. Danh sách 6 dữ liệu đầu vào bắt buộc để tính GEX, VEX, CHEX**  
Khác với GEX (chỉ số bậc 1\) có thể lấy sẵn cột Gamma từ Barchart rồi nhân với OI, hai chỉ số bậc 2 là **VEX (Vanna)** và **CHEX (Charm)** không được các trang web hiển thị sẵn mà code của anh phải tự tính từ công thức đạo hàm **Black-76** (dành cho Futures NQ) hoặc **Black-Scholes** (dành cho ETF QQQ / Index \$NDX).  
Dưới đây là bảng dữ liệu anh cần nạp vào code và trạng thái Real-time của từng biến số:

| Tên biến số | Ký hiệu trong công thức | Dùng để tính gì? | Có Miễn phí & Real-time không? |
| :---- | :---- | :---- | :---- |
| **1\. Giá tài sản cơ sở** | **${F}_{0}$** (Futures) hoặc ${S}_{0}$ (Spot) | GEX, VEX, CHEX (${d}_{1},{d}_{2}$) | **CÓ** (Real-time từng giây qua API chứng khoán hoặc TradingView) |
| **2\. Giá thực hiện (Strike)** | **$K$** | Cột mốc tính toán tại từng Strike | **CÓ** (Cố định theo chuỗi Options Chain) |
| **3\. Thời gian đáo hạn** | **$T$** (Tính bằng năm) | Cực kỳ quan trọng cho **CHEX** và **0DTE** | **CÓ** (Code tự đếm ngược từng phút đến giờ đáo hạn) |
| **4\. Độ biến động hàm ý (IV)** | **$\sigma$** (Implied Volatility) | Trái tim của **VEX (Vanna)** và ${d}_{1},{d}_{2}$ | **CÓ** (Real-time miễn phí qua Broker API, hoặc trễ 15p trên Barchart) |
| **5\. Khối lượng mở & Khối lượng khớp** | **$OI$** (Open Interest) & $Volume$ | Nhân với Greeks để ra tổng dòng tiền (\$M) | **Volume: Real-time OI: Cập nhật 1 lần/ngày** (Quy định chung của sàn) |
| **6\. Lãi suất phi rủi ro** | **$r$** (Lãi suất USD / SOFR) | Chiết khấu dòng tiền ${e}^{-rT}$ | **CÓ** (Hằng số cố định trong ngày, hiện tại nhập khoảng 0.04 \- 0.045) |

* **Công thức nhân quy mô (Multiplier) trong Code:**  
  * Để ra con số triệu đô (\$M) như trên Panel 1 và Panel 3 của anh:  
  * $NetGE{X}_{K}=(O{I}_{Call}\times {\Gamma }_{Call}-O{I}_{Put}\times {\Gamma }_{Put})\times Multiplier\times {F}_{0}$.  
  * $NetVE{X}_{K}=(O{I}_{Call}\times Vann{a}_{Call}-O{I}_{Put}\times Vann{a}_{Put})\times Multiplier\times {F}_{0}$.  
  * $NetCHE{X}_{K}=(O{I}_{Call}\times Char{m}_{Call}-O{I}_{Put}\times Char{m}_{Put})\times Multiplier\times {F}_{0}$.  
  * (Trong đó $Vanna=\frac{\partial \Delta }{\partial \sigma }=-{e}^{-rT}N'({d}_{1})\frac{{d}_{2}}{\sigma }$, còn $Charm=-\frac{\partial \Delta }{\partial T}$ như công thức Black-76 anh đã có. Với mã **NQ**, $Multiplier=20$; với **QQQ** hoặc **\$NDX**, $Multiplier=100$).

**2\. Sự thật về "Real-time" trong dữ liệu Quyền chọn (Điều 99% người mới hiểu lầm)**  
Khi anh hỏi có dữ liệu **Real-time miễn phí** không, anh cần tách bạch 2 phần:

* **Phần KHÔNG BAO GIỜ có Real-time (kể cả trả hàng chục nghìn USD/tháng): Đó là Open Interest ($OI$).**  
  * Theo cơ chế thanh toán bù trừ của Sở giao dịch CME và OCC (Options Clearing Corporation) tại Mỹ, **Open Interest ($OI$) chỉ được chốt sổ và công bố ĐÚNG 1 LẦN MỖI NGÀY** vào sáng sớm hôm sau (khoảng 13:00 – 15:00 chiều giờ VN, trước khi phiên Mỹ mở cửa). Ngay cả các quỹ Hedge Funds lớn nhất Phố Wall cũng dùng cùng một con số OI tĩnh đầu ngày này\!  
* **Phần CÓ Real-time (Nhảy từng giây trong phiên): Đó là Giá (${F}_{0}$), Độ biến động ($\sigma$ \- IV), Thời gian ($T$) và Khối lượng giao dịch trong ngày ($Volume$).**  
  * Dù OI đứng yên trong phiên, nhưng khi giá NQ chạy lên xuống, thời gian $T$ cạn dần từng phút và IV co giãn, các chỉ số **Gamma, Vanna, Charm tại từng Strike sẽ thay đổi Real-time**\!  
  * Ngoài ra, đối với quyền chọn đáo hạn trong ngày (**0DTE**), các trader định lượng sẽ dùng thêm cột **Intraday Volume (Khối lượng khớp lệnh Real-time)** cộng hoặc so sánh với **OI đầu ngày** (như Panel 2 Volume vs OI của anh) để phát hiện các "bức tường mới" được xây dựng ngay trong phiên.

**3\. Ba cách lấy dữ liệu Miễn phí cho Nasdaq (NQ / QQQ) từ dễ đến tự động hóa 100%**  
Vì sàn CME thu phí bản quyền dữ liệu Real-time của hợp đồng tương lai (NQ / GC) rất đắt, nhưng thị trường chứng khoán Mỹ lại cho phép lấy dữ liệu của quỹ ETF **QQQ** (bản sao 1:1 của Nasdaq-100) cực kỳ cởi mở, anh có 3 phương án sau:

> 1. **Phương án 1: Lấy trực tiếp từ Barchart hoặc CME QuikStrike (Miễn phí, giống hệt cách anh làm với Vàng)**  
   * **Cách làm:** Gõ mã **NQZ26** trên Barchart (hoặc vào công cụ miễn phí **CME QuikStrike** trên trang chủ cmegroup.com).  
   * **Độ trễ:** Dữ liệu **OI** là chuẩn 100% của cả ngày hôm đó. Dữ liệu **Giá, Volume và IV** trên bản miễn phí của Barchart bị **trễ 10 – 15 phút**.  
   * **Mẹo biến thành Real-time:** Anh lấy bảng OI và IV từ Barchart nạp vào code mỗi ngày trước giờ mở cửa phiên Mỹ (20:00 tối VN). Sau đó, trong phiên, anh chỉ cần nhập **giá NQ Real-time** (xem trên TradingView hoặc MT5 của quỹ) vào biến ${F}_{0}$. Code của anh sẽ tự động tính lại ${d}_{1},{d}_{2}$ và xuất ra biểu đồ **GEX, VEX, CHEX Real-time** theo đúng mức giá hiện tại\!  
> 2. **Phương án 2: Dùng thư viện Python yfinance quét mã QQQ hoặc ^NDX (Miễn phí 100%, Tự động hóa bằng Code)**  
   * Nếu anh không muốn tải file hay copy/paste thủ công từ Barchart cho mã NQZ26, anh có thể cho code Python gọi thẳng thư viện **yfinance** (Yahoo Finance) với mã **QQQ** (Invesco QQQ ETF) hoặc **^NDX** (Nasdaq-100 Index).  
   * Toàn bộ chuỗi Options Chain (Strike, Call/Put OI, Volume, Implied Volatility) của QQQ và ^NDX được trả về thẳng trong code chỉ bằng 3 dòng lệnh. Vì QQQ, ^NDX và NQ là cùng một rổ 100 cổ phiếu công nghệ Mỹ, mọi bức tường **Call Wall, Put Wall, Zero Gamma** trên QQQ và ^NDX khi quy đổi theo tỷ lệ Basis sang NAS100 (trên MT5) đều trùng khớp hoàn toàn với NQ\!  
> 3. **Phương án 3: Dùng API Real-time miễn phí của Tradier hoặc Schwab Developer (Chuẩn Real-time từng giây)**  
   * Nếu anh muốn cả cột **Implied Volatility (IV)** và **Intraday Volume** tự động cập nhật Real-time từng giây mà không trễ 15 phút, anh có thể đăng ký một tài khoản Developer miễn phí tại **Tradier** (gói Sandbox/Free API) hoặc **Polygon.io / Massive** (gói Free) để lấy chuỗi Options của QQQ / NDX qua REST API nạp thẳng vào hệ thống 3 Panel.

Hiện tại hệ thống 3 Panel của anh đang được viết bằng ngôn ngữ gì (Python, Pine Script trên TradingView, hay Web/Excel) và anh đang nạp dữ liệu từ Barchart vào bằng cách tải file CSV hay copy/paste? Em có thể viết sẵn đoạn code tự động kéo dữ liệu của Nasdaq cho đúng nền tảng anh đang dùng\!