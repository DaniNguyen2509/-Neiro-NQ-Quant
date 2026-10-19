# ADR-001: Cloud-Native Automation & Black-76 Quant Pipeline cho E-mini Nasdaq

## Status
Accepted

## Date
2026-10-19

## Context
Trước đây, hệ thống định lượng Options phụ thuộc vào:
1. Google Colab Notebook hoặc script cục bộ chạy thủ công trên máy tính người dùng.
2. Ý tưởng ban đầu sử dụng Playwright Chromium headless cào dữ liệu Barchart Futures Options NQ, vốn cồng kềnh (tải 300MB trình duyệt), dễ bị Cloudflare chặn bot, và tốn thời gian khởi tạo runner.
3. Cần đồng bộ hóa liên tục dữ liệu Options để phát hiện áp lực phòng hộ Dealer (GEX, VEX, CHEX), xác lập Call/Put Wall và Synthetic ATM Pivot phục vụ giao dịch E-mini Nasdaq-100 Futures (`NQ`), Micro E-mini (`MNQ`) và Spot Broker (`NAS100` / `US100`).

## Decision
1. **Kiến trúc Cloud-Native 100% trên GitHub Actions**:
   - Thiết lập workflow tự động [`.github/workflows/daily_options_sync.yml`](file:///c:/Users/Daniel/Documents/My-Projects/Neiro-NQ-Quant/.github/workflows/daily_options_sync.yml) không phụ thuộc máy tính cá nhân.
   - Áp dụng **Lưới Cron Đa Tầng Pre-Session Radar & Dual-Stage 0DTE Thích Ứng 2 Mùa** (14 lần chạy/ngày, `Thứ 2 - Thứ 6`), bao quát:
     * **07:15 VN (`15 0 * * 1-5`):** Chốt Open Interest từ CME Clearing & OCC cố định cho cả ngày.
     * **Phiên Âu 2 nấc (`30 5,6,7,8 * * 1-5`):** Radar tiền phiên (12:30/13:30 VN) và In-Session sau mở cửa London 30 phút (14:30/15:30 VN).
     * **Phiên Mỹ Full-Coverage (`45 11,12,13,14,15,16,17,18,19 * * 1-5`):** Đón đầu tin vĩ mô CPI/NFP (18:45 VN), bao trọn giờ mở cửa NYSE (19:45 - 21:45 VN), London Fix (23:45 VN), và **0DTE Power Hour Radar (02:45 VN)** trước giờ đóng cửa sàn New York.
2. **Nguồn Dữ liệu Tối ưu (yfinance QQQ -> NQ Mapping)**:
   - Sử dụng Invesco QQQ Trust Options làm proxy chuẩn mực (150+ strikes, đáo hạn 0DTE mỗi ngày, thanh khoản lớn nhất toàn cầu).
   - Tốc độ thực thi < 4 giây, không bị Cloudflare chặn, loại bỏ hoàn toàn Playwright và tiết kiệm 300MB headless browser bloat.
3. **Lõi Định lượng Black-76 cho Futures Options**:
   - Chuyển đổi từ mô hình Black-Scholes cơ bản sang mô hình Black-76 chuyên biệt cho Hợp đồng Tương lai (chiết khấu $e^{-rT}$).
   - Thuật toán giải ngược IV lai (Newton-Raphson + Brent bisection) ổn định cho 0DTE và OTM strikes.
   - Tính toán Put-Call Parity Synthetic Pivot, Net GEX ($M/1%), Net VEX, Net CHEX, và Brenner-Subrahmanyam Expected Move ($S_{\text{ATM}}/0.7979$).
4. **Bảng điều khiển Tác chiến Plotly Dark HUD**:
   - Layout 3 Panels thang giá ngang với thuật toán chống đè chữ (Anti-Collision).
   - 2 bảng chiến thuật: Intraday Scalping (30-50 pts) và Structural Swing Walls.
   - Hỗ trợ tham số `--basis` đồng bộ với sàn MT5.
5. **Triển khai Tự động lên GitHub Pages**:
   - Xuất bản Terminal tĩnh tương tác trực tiếp lên nhánh `gh-pages` để theo dõi qua link web trên mọi thiết bị di động/máy tính.

## Alternatives Considered

### Phương án A: Cào Barchart bằng Playwright Chromium
- **Ưu điểm**: Lấy trực tiếp mã hợp đồng tương lai NQ.
- **Nhược điểm**: Barchart bật Cloudflare Turnstile/Bot Management gắt gao; tốn 300MB cài đặt Chromium trên GitHub runner khiến thời gian build kéo dài 2-3 phút; rủi ro fail workflow cao.
- **Kết luận**: Loại bỏ.

### Phương án B: Trực tiếp Mua API CME DataMine / Databento
- **Ưu điểm**: Dữ liệu tick-by-tick real-time từ CME.
- **Nhược điểm**: Chi phí đắt đỏ ($100 - $500/tháng), vi phạm nguyên tắc mã nguồn mở & chi phí 0 VNĐ của dự án.
- **Kết luận**: Loại bỏ.

### Phương án C: Live yfinance Engine với QQQ Proxy (Được chọn)
- **Ưu điểm**: Miễn phí 100%, ổn định, tốc độ < 4s, 150+ strikes, 0DTE hàng ngày, không Cloudflare, không tốn tài nguyên máy chủ.
- **Kết luận**: Được chọn.

## Consequences
- Hệ thống hoạt động hoàn toàn tự động trên đám mây (Zero-Touch).
- Toàn bộ repo giữ mức siêu nhẹ **0.57 MB**, đáp ứng nghiêm ngặt Zero-Waste Mandate (< 15MB).
- Bộ test suite đạt 100% pass (14/14 tests).
- Nhà đầu tư có thể xem trực tiếp Terminal trên điện thoại qua GitHub Pages link.
