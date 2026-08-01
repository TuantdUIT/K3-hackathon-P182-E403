# BRIEF - Bản Tóm Tắt Dự Án

## 🎓 Agent Onboarding - Trợ Lý Ảo Cho Nhân Viên Sales Mới

---

## 💔 Vấn Đề (Problem Statement)

### Thực trạng onboarding nhân viên sales mới tại VinFast

| Vấn đề | Tác động |
|--------|----------|
| **Quy trình phức tạp** | Sales mới phải học 6 bước: Marketing → CRM → MXH → Tư vấn → Chốt deal → Dashboard |
| **SOP dài, khó nhớ** | Hàng trăm trang tài liệu nội bộ, không có ai hỏi 24/7 |
| **Sai sót khi thao tác** | Gọi nhầm khách, ghi nhầm đơn, bỏ sót bước checklist |
| **Không dám hỏi** | Sợ làm phiền quản lý, sợ bị đánh giá kém nên tự làm sai |
| **Tỷ lệ nghỉ việc cao** | 35% sales mới nghỉ trong 3 tháng đầu vì quá tải |

### Số liệu đáng chú ý
- **3-6 tháng** để sales mới đạt năng suất tối thiểu (theo nghiên cứu ngành bán lẻ ô tô)
- **40%** sai sót của sales mới đến từ việc quên quy trình, không phải thiếu năng lực
- **Mỗi lần sai** đều mất 30-60 phút để sửa, ảnh hưởng trải nghiệm khách hàng

---

## 💡 Giải Pháp (Solution)

### Agent Onboarding — Trợ lý AI đồng hành cùng sales mới trong 3 tháng đầu

```
┌─────────────────────────────────────────────────────────────────┐
│              NHÂN VIÊN SALES MỚI                                │
│                      │                                         │
│                      ▼                                         │
│      ┌──────────────────────────────┐                          │
│      │   🤖 AGENT ONBOARDING       │                          │
│      │   Hỏi đáp 24/7             │                          │
│      │   Hướng dẫn từng bước       │                          │
│      └──────────────────────────────┘                          │
│                      │                                         │
│       ┌──────────────┼──────────────┐                          │
│       ▼              ▼              ▼                          │
│   ┌────────┐    ┌────────┐    ┌────────┐                      │
│   │ CHAT   │    │COACHING│    │ CHECK │                      │
│   │ Hỏi đáp│    │Real-time│   │Kiểm tra│                     │
│   │ SOP/FAQ│    │ gợi ý  │    │năng lực│                     │
│   └────────┘    └────────┘    └────────┘                      │
└─────────────────────────────────────────────────────────────────┘
```

### Điểm khác biệt cốt lõi

| So sánh | Onboarding truyền thống | Agent Onboarding |
|---------|------------------------|------------------|
| Thời gian hỗ trợ | Giờ hành chính | 24/7 |
| Tốc độ phản hồi | Vài giờ → vài ngày | Tức thì |
| Cá nhân hóa | Không | Theo tiến độ từng người |
| Đánh giá năng lực | Thủ công, định kỳ | Tự động, liên tục |
| Chi phí | Cao (cần mentor riêng) | Thấp (1 agent phục vụ nhiều) |

---

## 👥 Đối Tượng Mục Tiêu

### Primary Users
- **Nhân viên Sales mới** tại showroom VinFast — vừa onboard, đang học quy trình

### Secondary Users
- **Sales Manager** — theo dõi tiến độ học việc của sales mới
- **Bộ phận Đào tạo (L&D)** — xây dựng và cập nhật tài liệu onboarding

---

## 👨‍💻 Thành Viên Nhóm

| STT | Họ và Tên | Discord ID | MSSV (5 số cuối) | Github User | Vai trò |
|:---:|:---|:---|:---:|:---|:---|
| 1 | Trần Dương Tuấn | tdtuit2023 | 01271 | TuantdUIT | Team Leader |
| 2 | Lại Thế Rin | ltrin1711 | 01665 | Rin171104 | AI Engineer |
| 3 | Cao Thị Thu Trang | channiedangiuu | 01885 | Channie1107 | Business Analyst |
| 4 | Bùi Thị Như Ngọc | nhungoc7811 | 01882 | ngocc19 | Business Analyst |

---

## 🚀 Phạm Vi MVP

### Quy trình 6 bước được hỗ trợ (theo sơ đồ nghiệp vụ)

| # | Bước | Agent hỗ trợ |
|---|------|--------------|
| 1 | Marketing Automation (FB/TikTok/Zalo) | Hướng dẫn cách chạy campaign cơ bản |
| 2 | CRM - Chấm điểm lead | Hướng dẫn phân loại lead nóng/lạnh |
| 3 | Tương tác qua MXH | Gợi ý kịch bản trả lời inbox, comment |
| 4 | Nuôi dưỡng lead | Gợi ý lịch nhắn tin, nội dung follow-up |
| 5 | Tư vấn - Lái thử - Báo giá | Hỗ trợ quy trình tư vấn 5 bước |
| 6 | Chốt deal & Ký hợp đồng | Checklist hợp đồng, giấy tờ cần thiết |

---

## 🔧 3 Hình Thức Hỗ Trợ Chính

### 1. Chat hỏi đáp
- Sales mới hỏi: *"Khách VIP yêu cầu giảm giá thêm 5 triệu, tôi có nên đồng ý không?"*
- AI trả lời dựa trên SOP, playbook, lịch sử xử lý

### 2. Co-pilot hỗ trợ real-time
- Khi sales đang chat với khách, AI gợi ý câu trả lời phù hợp
- Khi sales đang nhập CRM, AI cảnh báo nếu nhập sai

### 3. Đánh giá năng lực
- Chấm điểm tuần/tháng dựa trên số deal, tỷ lệ chốt, chất lượng thao tác
- Đề xuất lộ trình học tiếp theo

---

## 📅 Timeline

```
Week 1-2: Chat hỏi đáp SOP + 6 quy trình nghiệp vụ
Week 3:   Co-pilot real-time cho CRM + Tư vấn
Week 4:   Đánh giá năng lực + Dashboard cho Manager
```

---

## ✅ Checklist

- [x] Tên dự án: Agent Onboarding
- [x] Problem Statement: 35% sales mới nghỉ trong 3 tháng
- [x] Giải pháp AI: 3 hình thức hỗ trợ
- [x] Đối tượng: Nhân viên Sales mới
- [x] Phạm vi: Toàn bộ 6 bước nghiệp vụ
- [x] Thành viên: 3 người

---

*Document này được tạo cho VinFast K3 Hackathon - Team P182-E403*
