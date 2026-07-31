# Checklist viết `spec.md` — tóm tắt nội dung + lưu ý

> Bản rút gọn của `03-template-ai-spec.md` + `04-rubric.md`. Dùng để tự soát trước CP4.
> **Hạn cứng: commit `spec.md` trước 23:59 ngày 1 — quality bar chốt từ thời điểm này.**
> Spec gánh **56/75 điểm chấm** (R1 15 + R2 15 + R3 11 + R4 15).

---

## Bản đồ điểm — viết mục nào ăn điểm nào

| Mục spec | Khối rubric | Điểm |
|---|---|---|
| §1 + §2 | R1 · Bằng chứng & impact | 15 |
| §4 (gồm §4b) | R2 · Lát cắt & thiết kế | 15 |
| §5 + §6 | R3 · Chỗ khó & kịch bản | 11 |
| §7 (+ `eval/`) | R4 · Kiểm thử | 15 |
| §8 · §9 | hỗ trợ R6 (validation) + R7 (repo) | 11 |

---

## §1 · User & Job — cần viết gì

- [ ] **Job executor**: một vai cụ thể (`học viên ôn trước quiz`, `TA trả câu hỏi lặp`) — không phải "học viên nói chung".
- [ ] **Core JTBD** một câu `verb + object + bối cảnh`, **không có tên sản phẩm/AI trong câu**.
- [ ] **Problem statement**: ai — đang làm gì — vướng đâu — hậu quả gì. **Không chữ AI.**
- [ ] **Evidence** đạt ít nhất một chuẩn, log đầy đủ trong repo:
  - **Chuẩn A — khảo sát**: ≥20 người ngoài nhóm · ≥50% xác nhận · log đủ câu đã hỏi + **từng câu trả lời nguyên văn** + ai trả lời.
  - **Chuẩn B — mining**: số đếm được + **≥5 quote nguyên văn** + phương pháp đếm (đếm gì, trên bao nhiêu mẫu, quy tắc xếp loại).
- [ ] Đính kèm worksheet JTBD / ảnh sơ đồ.

**Lưu ý**
- Tự kiểm JTBD: *bỏ AI đi, việc đó còn tồn tại không?* Không còn → đang tìm chỗ nhét AI, chọn lại.
- Khảo sát hỏi về **lần gần nhất** ("lần gần nhất bạn muốn xem lại một đoạn bài giảng, bạn làm gì? mất bao lâu?"), **không** hỏi "bạn có cần tính năng X không?" — ai cũng trả lời có, dữ liệu vô dụng.
- "41/200 hội thoại mở đầu bằng tin không-phải-câu-hỏi" ✓ · "nhiều bạn nhắn linh tinh" ✗.
- **Không có log = không tính là bằng chứng**, dù nhóm có làm thật.

---

## §2 · Impact & quyết định chọn

- [ ] Bảng **≥3 ứng viên**, mỗi dòng có số: `bao nhiêu người gặp (từ evidence) | tần suất | mỗi lần tốn gì (phút/điểm/niềm tin) | build nổi không | chọn?`
- [ ] **Ứng viên ĐÃ LOẠI + lý do** — giữ nguyên trong spec, đừng xoá.
- [ ] Ứng viên CHỌN + lý do **bằng số**.

**Lưu ý**: hai ứng viên sát nhau → chọn cái có **bằng chứng mạnh hơn**. Người chấm cần thấy nhóm đã cân nhắc gì; spec chỉ có đúng một ý tưởng từ đầu là mất 3 điểm.

---

## §3 · Giải pháp tương tự

- [ ] Mỗi thành viên thử 1 sản phẩm gần giống (NotebookLM · Khanmigo · ChatGPT study mode · Quizlet AI...), 15'/người, trả lời đúng 4 câu: ① flow họ giải job này ② một điều đáng học ③ một điều đáng né ④ mình khác gì ở lát cắt này.

**Lưu ý**: "đáng học" phải là quan sát cụ thể — *"NotebookLM luôn cite nguồn cạnh câu trả lời"*, không phải *"giao diện đẹp"*.

---

## §4 · Thiết kế *(15đ — khối nặng nhất cùng R1/R4)*

- [ ] **Lát cắt MỘT CÂU**: 1 user · 1 việc · 1 quyết định AI · 1 kết quả — và **khớp bản build**. *(3đ)*
- [ ] **≥3 non-goals**, bản build không vi phạm. *(2đ)*
- [ ] **Mức prototype** khai báo: Sketch / Mock / Working + phần nào mock, phần nào thật. *(2đ ở R5)*
- [ ] **Automation**: augment / conditional / automate + lý do **theo cost-of-error**. *(4đ)*
- [ ] **§4b — bảng ≥4 nguyên tắc HAX/PAIR**, cột 2 là "áp cụ thể vào đâu trong prototype". *(6đ)*

**Chọn mức automation**

| Mức | Khi nào đúng |
|---|---|
| Augment — AI gợi ý, người quyết | Sai thì **đắt** (kiến thức sai đến học viên, điểm số) |
| Conditional — AI tự làm case chắc, chuyển người case mơ hồ | Đa số case lành, số ít hiểm |
| Automate — AI tự làm | Sai thì **rẻ**, user tự thấy và sửa được |

**Lưu ý**
- Lý do automation viết theo *sai thì ai chịu gì, sửa đắt hay rẻ* — **không viết "vì tiện"**.
- Nguyên tắc gợi ý: **G10 (thu hẹp phạm vi khi nghi ngờ) gần như bắt buộc**, cộng ≥1 trong G8 (gạt bỏ dễ) / G9 (sửa dễ) / G11 (giải thích vì sao), cộng ≥1 nhóm khởi đầu G1/G2.
- Mỗi nguyên tắc **phải chỉ ra được màn hình / câu chữ / nút cụ thể** — TA kiểm tại CP4. Khai chung chung = mất 6đ.

---

## §5 · Bốn lớp chỗ khó + ≥8 kịch bản

- [ ] Cụ thể hoá 4 lớp cho **lát cắt của mình** (không chép định nghĩa chung):
  - ① **Nguồn sự thật** — chỗ nào AI bịa được? Không có căn cứ thì làm gì?
  - ② **Mơ hồ / thiếu thông tin** — hỏi lại, đoán có báo, hay từ chối?
  - ③ **Ngoài phạm vi / thẩm quyền** — user sẽ đòi gì mà feature không được phép làm?
  - ④ **Đặc thù domain** — sai cái gì thì học viên học sai kiến thức / mất điểm / mất niềm tin?
- [ ] **≥8 kịch bản**, phủ đủ 4 lớp, mỗi dòng: `tình huống cụ thể | lớp | hành vi mong muốn (nói gì, hiện gì, cho user làm gì tiếp) | nguyên tắc áp`.

**Lưu ý**: chạy HAX Playbook (github.com/microsoft/HAXPlaybook) để sinh kịch bản. Tự kiểm — **kịch bản nào làm nhóm sợ nhất khi demo?** Chưa có cái nào đáng sợ = chưa đủ hiểm. Mỗi lớp phải có ≥2 case tương ứng trong golden set.

---

## §6 · Bốn đường đi của trải nghiệm

- [ ] Happy path · Low-confidence (②) · Failure/không căn cứ (①) · Correction (user sửa)
- [ ] Cộng: khi bị đòi ngoài phạm vi (③) · case đặc thù domain (④)

**Lưu ý**: 3 điểm chỉ được tính khi 4 đường đi **thể hiện trong prototype**, không chỉ nằm trên giấy. Demo nên bấm được ít nhất happy + 1 case chỗ khó.

---

## §7 · Kiểm thử *(15đ)*

- [ ] **Chiều chất lượng có định nghĩa kiểm chứng được** — tách chiều (đúng-có-căn-cứ / đúng cỡ-đúng giọng / an toàn), mỗi chiều pass/fail hoặc thang có mô tả mức. *(4đ)*
- [ ] **Golden set ≥20 case** trong `eval/`: ≥2 case/lớp chỗ khó + 8-10 case thường + 2-4 case hiếm, trong đó **≥10 case từ chatlog thật**. *(4đ)*
- [ ] **Quality bar bằng con số**: "Đạt khi ≥ __% qua bộ, và [điều kiện cứng]". *(3đ)*
- [ ] **Bảng kết quả** ≥1 lượt chạy trọn bộ, đủ mọi case kể cả fail, có %, đối chiếu bar; chưa đạt thì phân tích nguyên nhân. *(4đ)*

**Quy trình rút gọn**: chạy tay 10-20 input → ghi thô (dùng được / sửa được / không chấp nhận được) → **đặt tên cho từng nhóm lỗi** → chưng cất thành tiêu chí → 2 người chấm độc lập 5 output, lệch thì viết lại định nghĩa → dựng golden set → chốt bar → đo.

**Nhịp lặp**: `chạy trọn bộ → bảng % → chọn MỘT failure đau nhất → sửa → chạy lại TRỌN BỘ`.

**Lưu ý — ba lỗi kinh điển**
- Golden set toàn case dễ (TA kiểm độ phủ 4 lớp).
- Chấm "đạt" theo cảm tính giữa chừng → quay lại định nghĩa trong spec.
- **Đổi quality bar khi thấy kết quả thấp** → bar đã chốt lúc 23:59 N1. Không đạt bar mà **phân tích được nguyên nhân vẫn tính đủ điểm**; số liệu bị chỉnh sửa hoặc che giấu thì không tính.

---

## §8 · Phân công & kế hoạch

- [ ] Phân công **có tên** cho: spec / evidence / prompt / code / demo
- [ ] **≥3 willing users có tên** + kế hoạch validation CP5 (3 câu hỏi, ai log)
- [ ] Multi-prototype (nếu làm): ≥2 phương án **khác nhau ở một trục thiết kế có tên** + lý do chọn

**Lưu ý**: **vibe-coding rule** — CP5 hỏi ngẫu nhiên, không giải thích được phần có tên mình thì phần đó 0 điểm. Ba câu hỏi validation: *"Điều gì khó hiểu hoặc khó chịu nhất?"* · *"Kết quả này bạn có tin không — vì sao?"* · *"Bạn có dùng thật không — vì sao / vì sao chưa?"*

---

## §9 · Changelog

- [ ] Bảng `Thời điểm | Đổi gì | Vì sao (trỏ về feedback/case nào)`
- [ ] **≥1 thay đổi đến từ feedback user**, hoặc giữ nguyên có lý do căn cứ *(4đ ở R6)*

---

## Tự soát trước CP4

- [ ] Spec đủ §1-§9 theo `03-template-ai-spec.md`
- [ ] Evidence đạt chuẩn A và/hoặc B, **có log**
- [ ] Bảng impact ≥3 ứng viên + ứng viên đã loại
- [ ] 4 lớp cụ thể hoá + ≥8 kịch bản
- [ ] ≥4 nguyên tắc, mỗi cái có "áp vào đâu"
- [ ] Quality bar bằng %
- [ ] Kế hoạch sáng N2: ai validate, ai dry run
- [ ] **Commit `spec.md` trước 23:59 ngày 1**

## Lưu ý xuyên suốt

1. Rubric chấm **chuỗi quyết định và bằng chứng**, không chấm mức độ hoành tráng. Một bản Sketch làm kỹ > một bản Working làm vội.
2. Mọi con điểm phải **trỏ về một file trong repo** — viết xong phần nào thì commit phần đó.
3. **Ghi nhận trung thực** kết quả đo, kể cả khi không đạt bar.
4. Sau CP4 **không thêm feature mới**.
5. Không commit API key · chỉ dùng `data/` hoặc data giả · **không commit data pack** vào repo nộp bài (chỉ trích ngắn vài dòng, hoặc ghi mã đoạn/mã hội thoại).
