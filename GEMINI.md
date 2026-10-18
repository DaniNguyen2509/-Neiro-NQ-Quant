# GEMINI.md - Quy tắc cốt lõi cho Google Gemini & Antigravity IDE
> File này được nạp tự động vào ngữ cảnh của Google Gemini mỗi phiên làm việc tại Neiro-Quant.

---

## 1. QUY TRÌNH BẮT BUỘC TRƯỚC MỌI HÀNH ĐỘNG (PRE-ACTION SKILL DISCOVERY)

> **BƯỚC 0: TRƯỚC KHI TRẢ LỜI, PHÂN TÍCH HAY CHỈNH SỬA CODE:**
> Gemini **BẮT BUỘC** phải gọi tool iew_file để đọc nội dung file SKILL.md tương ứng trong thư mục .agents/skills/.
> Tuyệt đối không được bỏ qua bước này.

### 1.1. Bằng chứng bắt buộc trong mỗi câu trả lời (Mandatory Status Header)
Bắt đầu mỗi câu trả lời gửi đến người dùng, Gemini **PHẢI** xuất ra dòng trạng thái:
- Nếu áp dụng skill:
  [Active Skill: <tên-skill> | Path: .agents/skills/<tên-skill>/SKILL.md]
- Nếu là câu chào hỏi / xã giao thuần túy:
  [Active Skill: None | Reason: <lý do ngắn gọn>]

### 1.2. Chống lách luật (Anti-Rationalization Gate)
Nghiêm cấm Gemini tự đưa ra các lý do sau để bỏ qua việc mở skill:
- Yêu cầu này đơn giản tôi có thể giải quyết ngay -> **CẤM**
- Tôi đã có đủ kiến thức trong prompt -> **CẤM**
- Tôi sẽ trả lời trước rồi mới gọi skill sau -> **CẤM**

---

## 2. BẢNG ÁNH XẠ NHANH
*(Xem bảng đầy đủ tại [AGENTS.md](AGENTS.md))*

---

## 3. LUẬT BẤT DI BẤT DỊCH TẠI NEIRO-QUANT

1. **Nguồn sự thật:** [docs/spec.md](docs/spec.md) & [docs/architecture.md](docs/architecture.md). Mã nguồn thực tế có quyền lực tối cao nếu có mâu thuẫn.
2. **Không đổi cấu hình mặc định** của indicator đã có (2TC-v10, Neiro-Liquidity-Map-v2).
3. **ASCII và KHÔNG EMOJI** trong code MQL5. Pine và Markdown dùng tiếng Việt có dấu.
4. **Không tự chế luật hoặc backtest ngoài lề.** Mọi thay đổi logic do owner trực tiếp chỉ đạo.
5. **Performance constraints:** Python code phải đảm bảo CPU < 5%, RAM cố định, zero memory leak.


---

## 🧹 3. QUY ĐỊNH BẮT BUỘC: DỌN RÁC & BẢO TỒN DUNG LƯỢNG MÁY TÍNH (ZERO-WASTE MANDATE)

> [!CRITICAL]
> **TIÊU CHUẨN DUNG LƯỢNG TỐI THIỂU CHO MÁY TÍNH CỦA NGƯỜI DÙNG:**
> Toàn bộ dự án phải luôn được giữ ở mức siêu nhẹ (< 15MB). Mọi AI model khi thực thi đều phải tuân thủ nghiêm ngặt:
> 1. **Tự động dọn rác ngay lập tức:** Mọi file cào thử nghiệm (HTML/JSON tạm), script test scratch, file log tạm thời sinh ra trong quá trình nghiên cứu bắt buộc phải bị XÓA SẠCH SẼ ngay sau khi tác vụ hoàn thành.
> 2. **Không xả rác vào thư mục gốc:** Không tạo các file rác, file backup đuôi .bak, .tmp bừa bãi.
> 3. **Tận dụng đám mây (Cloud-First):** Ưu tiên chạy tính toán trên Google Colab / Codespaces, không cài đặt các gói dữ liệu nặng vào ổ cứng laptop của người dùng nếu không có yêu cầu rõ ràng.
