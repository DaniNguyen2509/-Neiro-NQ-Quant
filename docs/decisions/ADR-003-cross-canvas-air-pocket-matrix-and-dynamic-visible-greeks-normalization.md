# ADR-003: Tích Hợp Xuyên Suốt Vùng Chân Không Air Pocket Lên Cột Greeks Orderflow & Chuẩn Hóa Thang Đo Thích Ứng Dynamic Visible Normalization Cho Vanna/Charm (Thị Trường E-mini Nasdaq NQ)

- **Trạng thái:** ACCEPTED
- **Ngày quyết định:** 2026-11-02
- **Tác giả:** Neiro Quant Engineering Team
- **Tham chiếu:** [docs/spec.md](../spec.md), [docs/architecture.md](../architecture.md), [ADR-002](ADR-002-dual-view-terminal-and-black76-microstructure.md).

---

## 1. Bối cảnh & Vấn đề Cần Khắc Phục (Context & Problem Statement)

Trong quá trình vận hành hệ thống Canvas Orderflow Footprint trên thị trường E-mini Nasdaq-100 Futures (`NQ`), hệ thống ghi nhận 2 khiếm khuyết hiển thị vi cấu trúc:

1. **Cột VEX (Vanna) và CHEX (Charm) bị teo nhỏ vô hình (`< 0.05px`):**
   - Thuật toán Canvas cũ tính độ dài thanh bar (`len`) bằng cách chuẩn hóa tuyến tính với giá trị cực đại toàn chuỗi options (`globalMaxAbs`).
   - Tại các Strike OTM rất xa của NQ/QQQ tích tụ khối lượng OI/Volume khổng lồ, đẩy Vanna toàn chuỗi lên mức cực lớn.
   - Ngược lại, tại vùng giá giao dịch hiện tại gần ATM, các mức Vanna/Charm cục bộ chỉ chiếm tỷ lệ vô cùng nhỏ khi chia cho `globalMaxAbs`, bị trình duyệt khử răng cưa làm mờ và trader nhìn vào thấy cột như trống trơn.

2. **Túi chân không Air Pocket chưa hiển thị hoặc bị che khuất trong cột Greeks:**
   - Dữ liệu Air Pocket ở tầng Python trước đây chưa được quét mở rộng cho cấu trúc thị trường NQ và bị gán cứng rỗng trong một số luồng feed.
   - Trên Canvas: Lớp phủ 4 cột Greeks bên phải che đè lên dải chân không; thiếu hệ thống cảnh báo trực quan hai chiều (Main Candlestick Chart + Right Greeks Panel) để ngăn chặn việc đặt lệnh Limit chặn đầu xe.

---

## 2. Quyết định Thiết kế & Giải pháp Kỹ thuật (Architectural Decisions)

### 2.1. Phân Loại & Đặc Thù Hóa Cho Thị Trường E-mini Nasdaq (NQ-Specific Adaptation)
- **Đơn vị & Bước giá:** NQ sử dụng điểm chỉ số (points) với bước nhảy 25.0 - 50.0 điểm, nhãn hiển thị trực tiếp theo chuẩn CME Globex (`NQ 28,750`).
- **Phạm vi quét vi cấu trúc:**
  * Quét túi chân không thanh khoản lân cận giữa giá hiện tại và các Major Wall (`put_wall`, `call_wall`).
  * Mở rộng quét tầng sâu: bên dưới Put Wall (`major_down_wall - 150` đến `major_down_wall`) và bên trên Call Wall (`major_up_wall` đến `major_up_wall + 150`), phù hợp với biên độ di chuyển trung bình ngày của chỉ số Nasdaq.
  * Bộ lọc khoảng cách tối thiểu: `gap = abs(p_to - p_from) >= 5.0` (khử nhiễu các bước nhảy nhỏ).
  * Cơ chế dự phòng thông minh (Intraday Liquidity Fallback): khi hợp đồng 0DTE mới niêm yết trong ngày chưa qua chu kỳ thanh toán bù trừ qua đêm (OI = 0), thuật toán tự động sử dụng Volume giao dịch thực tế trong phiên làm proxy đo lường mật độ thanh khoản.

### 2.2. Trích Xuất An Toàn & Đa Hình (Polymorphic Extraction)
- Tầng Python chuẩn hóa trích xuất an toàn trên cả đối tượng `AirPocketZone` (`start_strike`, `end_strike`), `AirPocket` (`low_strike`, `high_strike`) và cấu trúc dictionary (`from`, `to`, `strike_nq`).
- Cập nhật `LevelStateMachine` xử lý trích xuất đa hình không gây lỗi `KeyError`.

### 2.3. Dynamic Visible Normalization & Square-Root Scaling
- Thay vì chuẩn hóa theo toàn chuỗi (`globalMaxAbs`), hệ thống tính toán `visibleMaxAbs` cục bộ cho từng cột (`GEX`, `VEX`, `CHEX`, `THETA`) dựa trên các strike đang hiển thị trong khung nhìn Canvas hiện tại (`y >= 28 && y <= h - 4`).
- Áp dụng thang đo phi tuyến lũy thừa (Square-Root Scaling):
  $$\text{scaled} = \left(\frac{|v|}{\text{visibleMaxAbs}}\right)^{0.50}$$
- Quy chuẩn độ rộng tối thiểu `minLen = 3.5px` cho mọi mốc có $|v| > 0.0001$, chiều cao thanh 6.0px kèm viền phản quang (`bPos`/`bNeg`), triệt tiêu hoàn toàn tình trạng thanh bar bị teo nhỏ vô hình.

### 2.4. Cross-Canvas Air Pocket Matrix & Interactive Tooltip
- **Thứ tự kết xuất Canvas chuẩn xác:**
  1. Vẽ nền tối bảo vệ cho Right Greeks Panel (`rgba(5, 7, 11, 0.82)`).
  2. Vẽ dải Air Pocket quét xuyên suốt:
     - Main Candlestick Chart: dải màu hổ phách `rgba(245, 158, 11, 0.12)`, viền nét đứt `[4, 4]`, nhãn cảnh báo:
       `⚠️ AIR POCKET VACUUM [NQ from - to] · NGUY CƠ TRƯỢT DÀI (CẤM ĐỠ DAO / KHÔNG CHẶN ĐẦU XE)`
     - Right Greeks Panel: dải màu hổ phách `rgba(245, 158, 11, 0.22)`, viền nét đứt `[3, 3]`, badge cảnh báo nổi bật:
       `⚠️ AIR POCKET (CẤM ĐỠ) NQ from-to`
  3. Vẽ các đường key options levels (ngắt ở biên chart, không đè lên cột Greeks).
  4. Vẽ 4 cột Greeks Profile kèm phụ đề thang đo động (`±...M` hoặc `±...M/d`).
  5. Interactive Tooltip Card: bắt sự kiện di chuột `mousemove` trên cột Greeks, tự động gióng mốc Strike NQ gần nhất và hiển thị chi tiết thông số `GEX | VEX | CHEX`.

---

## 3. Hệ Quả & Kiểm Chứng (Consequences & Verification)

- **Hiển thị vi cấu trúc tối ưu:** Cột VEX và CHEX hiển thị to, rõ nét, có phụ đề biên độ và tự động co giãn theo vùng nến trader đang zoom in/out.
- **Bảo vệ rủi ro tức thì:** Vùng chân không Air Pocket quét xuyên suốt cả nến và 4 cột Greeks, kèm badge cảnh báo trực diện `CẤM ĐỠ`, loại bỏ nguy cơ đặt limit chặn đầu xe.
- **Kiểm thử tự động:** Toàn bộ 18/18 unit tests vượt qua 100% (`18 passed`).
- **Dung lượng dự án:** Toàn bộ repository duy trì ở mức 1.38 MB, tuân thủ nghiêm ngặt Zero-Waste Mandate (< 15MB).

