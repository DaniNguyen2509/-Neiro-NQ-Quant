Chuyển từ Vàng (GC) sang **E-mini Nasdaq-100 Futures (NQ)** là một bước đi cực kỳ hợp lý cho hệ thống 3 Panel (GEX, VEX, CHEX) của anh.  
Lý do anh thấy Vàng hay chạy "lệch" hoặc quét râu xuyên qua các bức tường Gamma (như cú nhúng thủng 4,100 về 4,082 vừa rồi) là vì Vàng bị chi phối nặng bởi **thị trường vật chất ngầm tại London (OTC Spot/Forwards)**, dòng tiền ngân hàng trung ương và các tin tức địa chính trị bất ngờ nằm ngoài sổ lệnh quyền chọn sàn COMEX. Ngược lại, **Nasdaq (NQ) là sân chơi thuần túy 100% của thuật toán định lượng và phái sinh Mỹ** — nơi mọi cú giật giá đều tuân thủ cơ học Delta/Gamma Hedging của Market Makers (MM) một cách chuẩn xác hơn rất nhiều.  
Dưới đây là toàn bộ "Bản đồ chuyển đổi" từ Vàng sang **E-mini Nasdaq (NQ)** để anh cấu hình lại hệ thống và giao dịch thực chiến:  
**1\. Bảng quy đổi Thông số Kỹ thuật: Từ Vàng (GC) sang Nasdaq (NQ)**  
Để nạp dữ liệu vào code và tính toán rủi ro trên tài khoản quỹ, anh cần nắm rõ sự khác biệt về cấu trúc mã giữa hai thị trường:

| Hạng mục | Thị trường Vàng (Hệ thống cũ) | E-mini Nasdaq Futures (Hệ thống mới) |
| :---- | :---- | :---- |
| **Mã Hợp đồng Tương lai (CME)** | **GC** (Ví dụ hiện tại: GCZ26) | **NQ** (Hiện tại là kỳ tháng 12: **NQZ26**) |
| **Mã nối tiếp trên TradingView** | **GC1\!** | **NQ1\!** |
| **Mã trên Tài khoản Quỹ (CFD)** | **XAUUSD** | **NAS100** / **USTEC** / **US100** |
| **Hệ số nhân hợp đồng (Multiplier)** | **\$100** / 1 điểm giá (100 troy oz) | **\$20** / 1 điểm chỉ số (Bản Micro MNQ \= \$2/điểm) |
| **Chu kỳ kỳ hạn chính (Rollover)** | 5 tháng chẵn (G, J, M, Q, Z) | **4 tháng Quý** (H Tháng 3, M Tháng 6, U Tháng 9, Z Tháng 12\) |
| **Chỉ số đo biến động (Vega / IV)** | **GVZ** (Gold VIX) | **VXN** (CBOE Nasdaq Volatility Index) |

(Lưu ý khi sửa Code tính GEX: Trong công thức tính Net GEX của Vàng, anh nhân với 100 vì hệ số nhân của GC là 100 oz. Khi chuyển sang NQ, anh đổi hệ số nhân trong code thành **20**).  
**2\. Bí quyết lấy dữ liệu Options trên Barchart cho NQ (Không bị loạn kỳ hạn)**  
Khác với Vàng thường bị lộn xộn giữa kỳ hạn Tuần và Tháng, quyền chọn của Nasdaq (NQ) có **Quyền chọn đáo hạn mỗi ngày (0DTE \- Daily Expirations từ Thứ Hai đến Thứ Sáu)**. Đây chính là điểm giúp anh đánh Intraday (trong ngày) cực kỳ chuẩn xác:

* **Cách tra trên Barchart:** Anh gõ mã **NQZ26** $\rightarrow$ Vào mục **Options Prices**.  
* **Chọn kỳ đáo hạn nào để nạp vào 3 Panel?**  
  * **Để đánh lướt sóng trong phiên Mỹ hôm đó:** Anh chỉ cần chọn đúng kỳ đáo hạn của **ngày hôm đó (0DTE)** và **ngày mai (1DTE)**. Vì thời gian đáo hạn $T\rightarrow 0$ tính bằng giờ, chỉ số **Gamma ($\Gamma$)** và **Charm (CHEX)** của kỳ 0DTE lớn gấp hàng chục lần các kỳ hạn tháng. Mọi bức tường Call Wall / Put Wall của kỳ 0DTE chính là cản cứng thực sự của phiên hôm đó\!  
  * **Để nhìn biên độ lớn của tuần/tháng:** Anh kết hợp nhìn thêm bảng Options của quỹ ETF **QQQ** (tỷ lệ giá luôn bằng đúng **\~1/40** chỉ số Nasdaq, ví dụ NQ ở 20,000 thì QQQ ở 500\) hoặc chỉ số tiền mặt **\$NDX**. Các mốc số tròn trên NQ cách nhau mỗi **100 điểm** (ví dụ: 20,100; 20,200; 20,500) chính là nơi tập trung OI lớn nhất.

**3\. Ba quy luật vận hành của Nasdaq (NQ) giúp anh đánh chuẩn hơn Vàng**  
Khi đem bộ công cụ GEX, VEX, CHEX sang NQ, anh sẽ thấy thị trường chạy theo 3 đặc tính cơ học rất rõ ràng:

* **Thứ nhất: Cấu trúc "Put Skew" tạo lực đỡ Vanna/Charm cực mạnh (Ngược với Vàng)**  
  * Ở Vàng, đám đông sợ vàng bay mất nóc nên mua Call $\rightarrow$ tạo ra *Call Skew* (và Put hay bị IV Skew âm).  
  * Ở Nasdaq (NQ), các quỹ đầu tư luôn ôm cổ phiếu công nghệ nên họ rất sợ thị trường sập $\rightarrow$ họ liên tục mua **Put OTM** để bảo hiểm, khiến bảng Put của NQ luôn có **IV cao vút (Put Skew dương nặng)**.  
  * **Ứng dụng thực chiến:** Vì Put luôn đắt đỏ, nên trên Panel 3 của anh, các cột **CHEX Âm (thời gian trôi \= MM phải mua)** và **VEX Dương (IV giảm \= MM phải mua)** ở phía dưới giá hiện tại sẽ rất dày. Nếu không có tin tức vĩ mô quá xấu, cứ mỗi giờ trôi qua trong phiên Mỹ, thuật toán Charm và Vanna sẽ tự động ép MM **mua lại hợp đồng NQ**, tạo ra những phiên Nasdaq bò lên từ từ (Grind Up) hoặc rút chân chữ V cực nhanh khi chạm Put Wall.  
* **Thứ hai: "Giờ Vàng" mở cửa phiên Cơ sở Mỹ (20:30 giờ VN mùa Hè / 21:30 mùa Đông)**  
  * Khác với Vàng chạy rải rác từ phiên Á sang phiên Âu, 80% thanh khoản và dòng tiền Hedging của NQ bùng nổ vào lúc **09:30 sáng giờ New York (khi sàn chứng khoán Nasdaq mở cửa)**.  
  * **Kịch bản kinh điển mỗi tối:** Trong 15–30 phút đầu sau khi mở cửa (20:30 – 21:00 VN), thuật toán MM sẽ thực hiện tái cân bằng Delta đầu ngày — thường là một cú quét thẳng về **Put Wall** hoặc **Call Wall** gần nhất của kỳ 0DTE, sau đó rút chân và đi vào vùng **Sweet Spot (Trung hòa Delta)** để thu phí Theta.  
* **Thứ ba: Cách quy đổi Basis từ NQZ26 sang NAS100 (Tài khoản Quỹ)**  
  * Giống hệt như cách anh tính Basis giữa GCZ26 và XAUUSD, trên TradingView anh mở 2 mã: **NQZ26** (hoặc NQ1\!) và mã chỉ số của sàn quỹ (như **NAS100** hoặc **NDX**).  
  * Lấy giá NQZ26 trừ đi NAS100 để ra độ lệch **Basis** (ví dụ NQZ26 cao hơn NAS100 là \+85 điểm). Nếu hệ thống 3 Panel của anh báo **Call Wall tại 20,500** trên NQZ26, thì điểm đặt lệnh **Sell Limit** chuẩn xác trên MT5 của quỹ sẽ là: $20,500-85=20,415$.

Anh thử mở trang Barchart gõ mã **NQZ26** (chọn kỳ đáo hạn gần nhất đầu tuần tới) rồi chụp bảng Calls/Puts hoặc nạp thử vào code 3 Panel gửi lên đây, em sẽ cùng anh đọc vị ngay các bức tường Gamma đầu tiên trên Nasdaq nhé\!