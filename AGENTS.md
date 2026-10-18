# AGENTS.md - Quy tac cot loi cho moi AI Coding Agent
> Ap dung bat buoc cho: **Gemini, DeepSeek, Claude, Cursor, Copilot, OpenCode, Windsurf** va moi mo hinh AI khi hoat dong trong repository Neiro-Quant.

---

## 1. QUY TRINH TIEN TRAM BAT BUOC: GOI SKILL TRUOC MOI PHAN HOI

> **BUOC 0: TRUOC KHI SUY NGHI GIAI PHAP, TRA LOI HOAC SUA BAT KY DONG CODE NAO:**
> Moi model AI **BAT BUOC** phai truy cap vao thu muc .agents/skills/ va dung tool doc file (iew_file / 
ead_file) de nap file SKILL.md phu hop nhat voi yeu cau hien tai cua nguoi dung.

### 1.1. Header xac nhan bat buoc (Bang chung goi Skill)
O dau moi luot phan hoi cho nguoi dung, AI **bat buoc** phai ghi dong trang thai sau:
- Khi ap dung skill:
  [Active Skill: <ten-skill> | Path: .agents/skills/<ten-skill>/SKILL.md]
- Ngoai le duy nhat (cau chao hoi, hoi thoai thong thuong khong lien quan ky thuat/code):
  [Active Skill: None | Reason: <ly do ngan gon>]

### 1.2. Quy tac chong lach luat (Anti-Rationalization Gate)
Cac model **TUYET DOI KHONG DUOC** tu bien ho de bo qua viec goi skill.

---

## 2. BANG ANH XA NHANH: Y DINH (INTENT) -> SKILL BAT BUOC GOI

| Giai doan / Y dinh cua User | Ten Skill | Duong dan SKILL.md |
| :--- | :--- | :--- |
| **Chua ro lam gi / Can dinh huong** | using-agent-skills | .agents/skills/using-agent-skills/SKILL.md |
| **Lam ro yeu cau / Phong van lay spec** | interview-me | .agents/skills/interview-me/SKILL.md |
| **Phat trien y tuong / So sanh phuong an** | idea-refine | .agents/skills/idea-refine/SKILL.md |
| **Tinh nang moi / Thay doi kien truc** | spec-driven-development | .agents/skills/spec-driven-development/SKILL.md |
| **Lap ke hoach / Chia nho task** | planning-and-task-breakdown | .agents/skills/planning-and-task-breakdown/SKILL.md |
| **Viet code / Sua code / Trien khai** | incremental-implementation | .agents/skills/incremental-implementation/SKILL.md |
| **Code phuc tap, rui ro cao** | doubt-driven-development | .agents/skills/doubt-driven-development/SKILL.md |
| **Doi chieu tai lieu chuan / Verify API** | source-driven-development | .agents/skills/source-driven-development/SKILL.md |
| **Giao dien / Dashboard / Chart UI** | rontend-ui-engineering | .agents/skills/frontend-ui-engineering/SKILL.md |
| **Thiet ke API / Struct / Interface** | pi-and-interface-design | .agents/skills/api-and-interface-design/SKILL.md |
| **Thu thap context / Nap tai lieu repo** | context-engineering | .agents/skills/context-engineering/SKILL.md |
| **Viet test / TDD / Kiem thu logic** | 	est-driven-development | .agents/skills/test-driven-development/SKILL.md |
| **Sua loi / Debug / Bug** | debugging-and-error-recovery | .agents/skills/debugging-and-error-recovery/SKILL.md |
| **Review code / Danh gia chat luong** | code-review-and-quality | .agents/skills/code-review-and-quality/SKILL.md |
| **Toi uu code / Don gian hoa** | code-simplification | .agents/skills/code-simplification/SKILL.md |
| **Bao mat / Ra soat lo hong** | security-and-hardening | .agents/skills/security-and-hardening/SKILL.md |
| **Hieu nang / Toi uu toc do** | performance-optimization | .agents/skills/performance-optimization/SKILL.md |
| **Git / Commit / Branch** | git-workflow-and-versioning | .agents/skills/git-workflow-and-versioning/SKILL.md |
| **Viet tai lieu / ADR / Kien truc** | documentation-and-adrs | .agents/skills/documentation-and-adrs/SKILL.md |
| **Ship / Release / Dong goi** | shipping-and-launch | .agents/skills/shipping-and-launch/SKILL.md |

*(Neu khong biet chon skill nao, mac dinh nap .agents/skills/using-agent-skills/SKILL.md)*

---

## 3. CAC QUY TAC BAT DI BAT DICH CUA REPO NEIRO-QUANT

1. **Nguon su that:** docs/spec.md (kien truc he thong) va docs/architecture.md.
2. **Khong tu y doi tham so mac dinh** cua 2 indicator san co (2TC-v10, Neiro-Liquidity-Map-v2). Do la cau hinh song cua owner.
3. **ASCII va KHONG EMOJI:**
   - MQL5 (.mq5, .mqh): Comment tieng Viet **khong dau**, ASCII thuan.
   - Pine (.pine) va Markdown (.md): Tieng Viet co dau binh thuong.
   - Khong dung emoji trang tri trong code (chi cho phep cac ky hieu chart chuc nang).
4. **Khong tu che luat hoac backtest ngoai le:** Moi thay doi logic do owner truc tiep chi dao.
5. **Python code phai tuan thu performance constraints:** CPU < 5%, RAM co dinh, khong memory leak.


---

## 🧹 3. QUY ĐỊNH BẮT BUỘC: DỌN RÁC & BẢO TỒN DUNG LƯỢNG MÁY TÍNH (ZERO-WASTE MANDATE)

> [!CRITICAL]
> **TIÊU CHUẨN DUNG LƯỢNG TỐI THIỂU CHO MÁY TÍNH CỦA NGƯỜI DÙNG:**
> Toàn bộ dự án phải luôn được giữ ở mức siêu nhẹ (< 15MB). Mọi AI model khi thực thi đều phải tuân thủ nghiêm ngặt:
> 1. **Tự động dọn rác ngay lập tức:** Mọi file cào thử nghiệm (HTML/JSON tạm), script test scratch, file log tạm thời sinh ra trong quá trình nghiên cứu bắt buộc phải bị XÓA SẠCH SẼ ngay sau khi tác vụ hoàn thành.
> 2. **Không xả rác vào thư mục gốc:** Không tạo các file rác, file backup đuôi .bak, .tmp bừa bãi.
> 3. **Tận dụng đám mây (Cloud-First):** Ưu tiên chạy tính toán trên Google Colab / Codespaces, không cài đặt các gói dữ liệu nặng vào ổ cứng laptop của người dùng nếu không có yêu cầu rõ ràng.
