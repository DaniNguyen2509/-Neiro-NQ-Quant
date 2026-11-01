Bộ công thức toán học cốt lõi dưới đây tổng hợp toàn bộ nền tảng định lượng từ mô hình **Black-76** (chuẩn sàn CME cho hợp đồng tương lai Vàng GC và Nasdaq NQ) đến các chỉ số dòng tiền của Market Makers (**GEX, VEX, CHEX**) để anh đóng khung làm tài liệu tra cứu và lập trình:  
**1\. Nhóm biến số đầu vào & Định giá Hợp đồng Tương lai (Cost of Carry)**  
Trước khi tính quyền chọn, mối liên hệ giữa giá Hợp đồng tương lai (${F}_{0}$) và giá Giao ngay (${S}_{0}$) được xác định qua mô hình chi phí lưu giữ:  
**Công thức Cost of Carry (Tính giá lý thuyết của Futures):**

$${F}_{0}={S}_{0}\times {e}^{(r+u-y)\times T}$$

*   
  *(Với chỉ số chứng khoán như Nasdaq/S\&P 500 không tốn phí lưu kho $u$, công thức rút gọn thành ${F}_{0}={S}_{0}\times {e}^{(r-d)\times T}$, trong đó $d$ là tỷ suất cổ tức).*

**Độ lệch Basis (Quy đổi điểm vào lệnh giữa Futures và Spot/CFD):**

$$Basis={F}_{0}-{S}_{0}$$

$$ĐiểmvàolệnhtrênSpot/CFD=Strike{K}_{(trênFutures)}-Basis$$

* 

**Quy đổi Thời gian đáo hạn ($T$ — tính theo năm, chuẩn hóa đến từng phút cho 0DTE):**

$$T=\frac{Sốphútcònlạiđếngiờđáohạn}{365\times 24\times 60}=\frac{Sốphútcònlại}{525,600}$$

*   
  (Trong đó: ${F}_{0}$ là giá Futures hiện tại; $K$ là giá thực hiện/Strike; $r$ là lãi suất phi rủi ro USD $\approx 0.043$; $\sigma$ là Độ biến động hàm ý \- Implied Volatility đổi ra số thập phân).

**2\. Mô hình Black-76: Định giá Quyền chọn trên Hợp đồng Tương lai**  
Toàn bộ các chỉ số Greeks trên sàn CME đều xuất phát từ hai biến số trung gian ${d}_{1}$, ${d}_{2}$ và hàm phân phối chuẩn:  
**Biến số trung gian ${d}_{1}$ và ${d}_{2}$:**

$${d}_{1}=\frac{\ln \left({\frac{{F}_{0}}{K}}\right)+\left({\frac{{\sigma }^{2}}{2}}\right)T}{\sigma \sqrt{T}};{d}_{2}={d}_{1}-\sigma \sqrt{T}$$

* 

**Hàm mật độ xác suất chuẩn $N'({d}_{1})$ và Hàm phân phối tích lũy chuẩn $N(x)$:**

$$N'({d}_{1})=\frac{1}{\sqrt{2\pi }}{e}^{-\frac{{d}_{1}^{2}}{2}};N(x)=\int\limits_{-\infty }^{x}\frac{1}{\sqrt{2\pi }}{e}^{-\frac{{t}^{2}}{2}}dt$$

*   
  (Lưu ý: $N({d}_{2})$ chính là xác suất thực sự trong môi trường trung hòa rủi ro để quyền chọn đáo hạn ở trạng thái có lãi / In-The-Money).

**Giá lý thuyết của Quyền chọn Mua (Call \- $C$) và Bán (Put \- $P$):**

$$C={e}^{-rT}\left[{{F}_{0}\times N({d}_{1})-K\times N({d}_{2})}\right]$$

$$P={e}^{-rT}\left[{K\times N(-{d}_{2})-{F}_{0}\times N(-{d}_{1})}\right]$$

* 

**3\. Các chỉ số Hy Lạp Bậc 1 (First-Order Greeks)**  
Đo lường độ nhạy trực tiếp của giá quyền chọn và tỷ lệ phòng hộ (Hedge Ratio) của Market Makers:  
**Delta ($\Delta$ — Tốc độ thay đổi giá Option theo giá Futures / Tỷ lệ phòng hộ):**

$${\Delta }_{Call}=\frac{\partial C}{\partial {F}_{0}}={e}^{-rT}N({d}_{1});{\Delta }_{Put}=\frac{\partial P}{\partial {F}_{0}}=-{e}^{-rT}N(-{d}_{1})$$

*   
  *Tính chất ngang giá Put-Call:* \$\\vert{}\\Delta\_{\\text{Call}}\\vert{} \+ \\vert{}\\Delta\_{\\text{Put}}\\vert{} \= e^{-rT} \\approx 1.00\$. *Điểm trung hòa Delta tự nhiên (Mắt bão ATM):* Nơi ${\Delta }_{Call}\approx +0.50$ và ${\Delta }_{Put}\approx -0.50$, tức ${\Delta }_{Call}+{\Delta }_{Put}\approx 0$.

**Vega ($V$ hoặc $\nu$ — Độ nhạy của giá Option khi Độ biến động $\sigma$ thay đổi 1%):**

$$V=\frac{\partial V}{\partial \sigma }={F}_{0}\times {e}^{-rT}\times N'({d}_{1})\times \sqrt{T}$$

*   
  (Chia cho 100 nếu muốn tính số điểm thay đổi trên mỗi 1% IV; giống nhau cho cả Call và Put).

**Theta ($\Theta$ — Tốc độ hao mòn giá trị theo thời gian mỗi năm; chia 365 để ra mỗi ngày):**

$${\Theta }_{Call}=-\frac{{F}_{0}\times \sigma \times {e}^{-rT}\times N'({d}_{1})}{2\sqrt{T}}+r\times C$$

$${\Theta }_{Put}=-\frac{{F}_{0}\times \sigma \times {e}^{-rT}\times N'({d}_{1})}{2\sqrt{T}}+r\times P$$

* 

**4\. Các chỉ số Hy Lạp Bậc 2 (Second-Order Greeks — Vũ khí đọc vị Market Makers)**  
Đo lường tốc độ thay đổi của chính lượng hợp đồng phòng hộ ($\Delta$) khi Giá, Độ biến động hoặc Thời gian thay đổi:  
**Gamma ($\Gamma$ — Gia tốc của Delta khi giá cơ sở ${F}_{0}$ di chuyển 1 điểm):**

$$\Gamma =\frac{\partial \Delta }{\partial {F}_{0}}=\frac{{\partial }^{2}V}{\partial {F}_{0}^{2}}=\frac{{e}^{-rT}\times N'({d}_{1})}{{F}_{0}\times \sigma \sqrt{T}}$$

* 

**Vanna (Độ nhạy của Delta khi Độ biến động $\sigma$ thay đổi, hoặc độ nhạy của Vega theo giá ${F}_{0}$):**

$$Vanna=\frac{\partial \Delta }{\partial \sigma }=\frac{\partial V}{\partial {F}_{0}}=-{e}^{-rT}\times N'({d}_{1})\times \frac{{d}_{2}}{\sigma }$$

* 

**Charm (Tốc độ phân rã của Delta khi thời gian $T$ trôi qua — Delta Decay):**

$$Charm=-\frac{\partial \Delta }{\partial T}=\frac{\partial \Theta }{\partial {F}_{0}}$$

$$Char{m}_{Call(mỗingày)}=-\frac{{e}^{-rT}\left[{N'({d}_{1})\left({\frac{-{d}_{2}}{2T}}\right)+rN({d}_{1})}\right]}{365}$$

$$Char{m}_{Put(mỗingày)}=-\frac{{e}^{-rT}\left[{N'({d}_{1})\left({\frac{-{d}_{2}}{2T}}\right)-rN(-{d}_{1})}\right]}{365}$$

* 

**5\. Công thức Quy đổi ra Dòng tiền Thực chiến trên Hệ thống 3 Panel (OI Weighted)**  
Để biến các chỉ số lý thuyết ở trên thành quy mô tiền thật (\$M \- Triệu USD) mà Market Makers phải mua/bán tại từng mốc Strike $K$ (cộng gộp qua $n$ kỳ đáo hạn gần nhất)\[cite: 5, 7\], ta nhân với Khối lượng hợp đồng mở (\$\\text{OI}\$) và **Hệ số nhân hợp đồng (${M}_{contract}$)** *(với Vàng GC: ${M}_{contract}=100$; với Nasdaq NQ: ${M}_{contract}=20$; với S\&P 500 ES: ${M}_{contract}=50$)*:  
**Delta Ròng tại một Strike (Net Position Delta):**

$$NetDelt{a}_{K}=\sum\limits_{i=1}^{n}\left({O{I}_{Call,K,i}\times {\Delta }_{Call,K,i}+O{I}_{Put,K,i}\times {\Delta }_{Put,K,i}}\right)$$

* 

**Sức mạnh Tường Thanh khoản Thực tế (Dùng để lọc nhiễu giữa Weekly và Monthly):**

$$WallStrengt{h}_{K}=\sum\limits_{i=1}^{n}\left({O{I}_{K,i}\times {\Gamma }_{K,i}}\right)$$

* 

**Panel 1 — Net GEX (Phơi nhiễm Gamma ròng tại Strike $K$ tính bằng USD khi giá biến động 1%):**

$$NetGE{X}_{K}=\sum\limits_{i=1}^{n}\left({O{I}_{Call,K,i}\times {\Gamma }_{K,i}-O{I}_{Put,K,i}\times {\Gamma }_{K,i}}\right)\times {M}_{contract}\times {F}_{0}^{2}\times 0.01$$

*   
  (Nếu tính theo mỗi 1 điểm biến động của giá, bỏ phần $\times {F}_{0}\times 0.01$ và chỉ nhân $\times {M}_{contract}\times {F}_{0}$).

**Panel 3 — Net VEX (Phơi nhiễm Vanna ròng tại Strike $K$ khi IV thay đổi 1%):**

$$NetVE{X}_{K}=\sum\limits_{i=1}^{n}\left({O{I}_{Call,K,i}\times Vann{a}_{K,i}-O{I}_{Put,K,i}\times Vann{a}_{K,i}}\right)\times {M}_{contract}\times {F}_{0}\times 0.01$$

* 

**Panel 3 — Net CHEX (Phơi nhiễm Charm ròng — Dòng tiền tự động chảy mỗi ngày tại Strike $K$):**

$$NetCHE{X}_{K}=\sum\limits_{i=1}^{n}\left({O{I}_{Call,K,i}\times Char{m}_{Call,K,i}-O{I}_{Put,K,i}\times Char{m}_{Put,K,i}}\right)\times {M}_{contract}\times {F}_{0}$$

*   
* **Tổng tiền phí thời gian (Total Daily Theta Bleed) chảy vào túi MM tại một Strike:**  
  \$\$\\text{Total Theta}\_K (\\text{USD/ngày}) \= \\left( \\text{OI}\_{\\text{Call}, K} \\times \\vert{}\\Theta\_{\\text{Call}, K}\\vert{} \+ \\text{OI}\_{\\text{Put}, K} \\times \\vert{}\\Theta\_{\\text{Put}, K}\\vert{} \\right) \\times M\_{\\text{contract}}\$\$

**6\. Công thức Độ lệch Biến động (IV Skew) & Chỉ số Biến động Tổng hợp (GVZ / VXN / VIX)**  
**Độ lệch biến động tại từng Strike (IV Skew trên bảng Barchart):**

$$IVSke{w}_{K}={\sigma }_{K}-{\sigma }_{ATM}$$

*   
  (Nếu $IVSke{w}_{K}<0$: Vùng MM tự tin bán đè biến động / ghim giá; Nếu $IVSke{w}_{K}\gg 0$: Vùng đám đông FOMO mua đuổi, tiềm ẩn rủi ro nổ Gamma Squeeze)\[cite: 5, 7\].

**Phương sai kỳ vọng tổng hợp (Công thức chuẩn CBOE cho GVZ của Vàng, VIX của S\&P 500, VXN của Nasdaq):**

$${\sigma }_{Index}^{2}=\frac{2}{T}\sum\limits_{i}^{}\frac{\Delta {K}_{i}}{{K}_{i}^{2}}{e}^{rT}Q({K}_{i})-\frac{1}{T}{\left[{\frac{{F}_{0}}{{K}_{0}}-1}\right]}^{2}$$

*   
  (Trong đó $Q({K}_{i})$ là giá trung bình của các quyền chọn OTM tại mức giá ${K}_{i}$, $\Delta {K}_{i}$ là khoảng cách giữa các Strike, và ${K}_{0}$ là mốc Strike đầu tiên ngay dưới giá Futures ${F}_{0}$).

Anh muốn đi sâu vào giải thích chi tiết cách đạo hàm hoặc kiểm chứng bằng số thực tế cho công thức nào trong bộ trên trước?