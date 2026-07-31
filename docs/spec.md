# AI Spec — Trợ lý định giá xe cũ đổi xe điện VinFast

> Viết theo `docs/05-checklist-spec.md` (§1–§9).
>
> **Cách đọc file này.** Phần nào rút ra được từ mã nguồn thì đã viết đầy đủ và có
> trỏ `file:line` để người chấm mở ra đối chiếu. Phần nào cần dữ liệu do người thật
> tạo ra — khảo sát, tên thành viên, kết quả chạy đo — được đánh dấu
> **⚠ CẦN ĐIỀN** kèm khung sẵn. Không điền những ô đó thì mất điểm ở đúng khối
> tương ứng; checklist ghi rõ *"không có log = không tính là bằng chứng"*.

---

## §0 · Phạm vi lát cắt được chấm

Repo có **ba** agent dùng chung một giao thức con trỏ ảo:

| Agent | Màn hình | Vai trò trong spec này |
|---|---|---|
| `form_graph` (lái thử) | `/` — trang khách | Nền tảng có sẵn, **không** phải lát cắt được chấm |
| `crm_lead_agent` | `/admin-portal` — thêm khách | Nền tảng có sẵn, **không** phải lát cắt được chấm |
| **`swap_car_agent`** | `/admin-portal/dinh-gia` | **Lát cắt của spec này** |

Chọn `swap_car` vì đây là luồng duy nhất mà đầu ra của AI là **một con số tiền
báo cho khách** — cost-of-error đo được bằng tiền, nên các quyết định thiết kế ở
§4 có căn cứ để tranh luận. Hai luồng kia chỉ điền form rồi submit.

> ⚠ **CẦN NHÓM XÁC NHẬN**: nếu buổi demo định trình cả ba luồng thì phải sửa mục
> này, vì rubric §4 chấm *"lát cắt một câu và khớp bản build"*. Trình ba luồng mà
> spec mô tả một luồng là lệch.

---

## §1 · User & Job

### Job executor

**Nhân viên kinh doanh showroom VinFast đang ngồi trước khách muốn đổi xe xăng cũ
lấy xe điện, phải báo được con số "khách cần bù thêm bao nhiêu" ngay trong buổi
gặp.**

Không phải "nhân viên kinh doanh nói chung" — người này đang ở giữa một cuộc
thương lượng, có khách ngồi đối diện, và im lặng quá lâu là mất thế.

### Core JTBD

> Quy đổi tình trạng một chiếc xe cũ thành con số bù trừ đáng tin, ngay tại bàn
> làm việc, trong lúc khách còn ngồi đó.

*(Tự kiểm theo checklist: bỏ AI đi, việc này vẫn tồn tại — sales vẫn phải tra
bảng giá, chấm 8 tiêu chí, cộng trừ khuyến mãi bằng tay. ✓)*

### Problem statement

Nhân viên kinh doanh phải tự tra giá thị trường xe cũ, tự chấm 8 tiêu chí thẩm
định theo trọng số, rồi cộng trừ giá lăn bánh và các khoản ưu đãi để ra số tiền
khách bù thêm. Quy trình này nằm rải ở nhiều chỗ — bảng giá, bảng tiêu chí, bảng
phí — nên mỗi người làm một kiểu và làm chậm. Khách ngồi chờ, và một con số báo
sai thì hoặc showroom lỗ, hoặc khách mất niềm tin rồi bỏ đi.

*(Không có chữ AI trong đoạn trên — theo yêu cầu checklist.)*

### Evidence — ⚠ CẦN ĐIỀN

Checklist cho hai chuẩn, đạt **ít nhất một**:

**Chuẩn A — khảo sát** (≥20 người ngoài nhóm, ≥50% xác nhận)

```
Câu hỏi phải hỏi về LẦN GẦN NHẤT, không hỏi "bạn có cần tính năng X không":
  1. Lần gần nhất anh/chị báo giá đổi xe cho khách là khi nào?
  2. Lúc đó anh/chị tra giá xe cũ ở đâu, mất bao lâu?
  3. Có lần nào báo xong rồi phải sửa lại con số không? Vì sao?

Log bắt buộc lưu vào: eval/evidence/survey-log.md
  - đủ câu đã hỏi
  - TỪNG câu trả lời nguyên văn
  - ai trả lời (tên/vai trò, có thể ẩn danh hoá)
```

| # | Người trả lời | Vai trò | Trả lời nguyên văn | Xác nhận vấn đề? |
|---|---|---|---|---|
| 1 | | | | |
| … | | | | |

→ Tổng: __/20 người · __% xác nhận

**Chuẩn B — mining** (số đếm được + ≥5 quote nguyên văn + phương pháp đếm)

```
Nguồn khả dĩ: log chat Zalo/Messenger của showroom, biên bản thẩm định cũ,
              file Excel báo giá nội bộ.
Phải ghi rõ: đếm gì · trên bao nhiêu mẫu · quy tắc xếp loại.
```

> **Lưu ý về mức độ trung thực.** Đây là ô duy nhất trong spec không thể suy ra
> từ mã nguồn. Nếu nhóm chưa kịp khảo sát, hãy ghi thẳng *"chưa có evidence"*
> thay vì điền số ước đoán — checklist ghi rõ số liệu bị chỉnh sửa hoặc che giấu
> thì không tính điểm, còn thiếu mà thừa nhận thì chỉ mất điểm phần đó.

---

## §2 · Impact & quyết định chọn — ⚠ CẦN ĐIỀN CỘT SỐ

Bảng dưới đã liệt kê ba ứng viên có thật trong repo (hai cái đã build, một cái
đã cân nhắc). Cột số phải lấy từ evidence §1.

| Ứng viên | Bao nhiêu người gặp | Tần suất | Mỗi lần tốn gì | Build nổi? | Chọn? |
|---|---|---|---|---|---|
| **A. Định giá xe cũ đổi xe điện** | __ /20 | __ | Tra bảng + tính tay, __ phút; sai số tiền → mất khách | Có — công thức đã chốt trong `CAR_PREDICT_FORMULA.md` | ✅ **CHỌN** |
| B. Nhập lead hộ khách vào CRM | __ /20 | __ | Gõ lại form __ phút | Có — đã build `crm_lead_agent` | ❌ loại |
| C. Đặt lịch lái thử từ chat khách | __ /20 | __ | Khách tự điền được, sales không tốn công | Có — đã build `form_graph` | ❌ loại |

**Lý do loại B**: tiết kiệm thao tác gõ, nhưng sai thì sửa lại được ngay và
không ai mất tiền — cost-of-error thấp, giá trị chứng minh thấp.

**Lý do loại C**: người hưởng lợi là khách chứ không phải job executor ở §1, và
khách tự điền form cũng xong.

**Lý do chọn A — cần viết bằng số**: ⚠ điền theo mẫu *"__/20 sales gặp hàng tuần,
mỗi lần tốn __ phút và đã có __ trường hợp báo sai phải xin lỗi khách"*.

> Giữ nguyên hai dòng đã loại trong spec. Checklist ghi: spec chỉ có đúng một ý
> tưởng từ đầu là mất 3 điểm.

---

## §3 · Giải pháp tương tự — ⚠ CẦN ĐIỀN (15'/người)

Mỗi thành viên thử **một** sản phẩm, trả lời đúng bốn câu.

| Thành viên | Sản phẩm thử | ① Flow họ giải job này | ② Một điều đáng học | ③ Một điều đáng né | ④ Mình khác gì |
|---|---|---|---|---|---|
| | Carvana / Vroom (định giá xe cũ online) | | | | |
| | Bonbanh / Chotot Xe (định giá VN) | | | | |
| | ChatGPT + ảnh chụp xe | | | | |

**Gợi ý trục so sánh riêng của lát cắt này**: các sản phẩm trên đều bắt *khách*
tự nhập rồi trả về một khoảng giá. Lát cắt này ngược lại — người dùng là *sales*,
đầu vào là câu nói tự nhiên khi đang tiếp khách, và đầu ra phải là con số đơn trị
kèm đường đi của phép tính để sales đọc lại cho khách nghe.

> "Đáng học" phải là quan sát cụ thể — *"Carvana hiện luôn dải giá thay vì một
> số, kèm câu 'giá cuối phụ thuộc kiểm tra thực tế'"*, không phải *"giao diện đẹp"*.

---

## §4 · Thiết kế

### Lát cắt một câu

> **Một nhân viên kinh doanh** đọc tình trạng xe cũ bằng tiếng Việt tự nhiên,
> **AI quyết định** bóc tách thành 14 ô hồ sơ định giá và chấm 7 tiêu chí thẩm
> định, **kết quả** là số tiền khách cần bù thêm (C) kèm đường đi của phép tính —
> **sales soát và chốt ở ba điểm dừng**, AI không tự gửi gì cho khách.

Khớp bản build: `src/backend/agents/swap_car/graph.py`.

### Non-goals (≥3)

1. **Không tự áng giá xe không có trong bảng giá.** Không tra được `used_car_prices`
   thì dừng, chuyển thẩm định viên. Đã cưỡng chế bằng node `market_check`
   (`swap_car/nodes.py`, `graph.py` — nhánh `market_check → END`).
2. **Không tự bật cờ loại trừ cứng.** Bốn cờ (ngập nước, đâm đụng kết cấu, tua
   công-tơ-mét, thiếu giấy tờ) chỉ bật khi sales nói rõ. Prompt ghi thẳng:
   *"chỉ đặt true khi nhân viên NÓI RÕ là có… tuyệt đối không đặt false hay true
   để đoán"* (`swap_car/nodes.py:288`), và `_normalize` chỉ nhận `is True`
   (`nodes.py:251`).
3. **Không gửi báo giá cho khách.** Agent chỉ ghi hồ sơ và hiện số cho sales;
   mọi việc nói với khách do sales làm.
4. **Không thay thẩm định viên.** Tiêu chí sales chưa chấm thì tạm tính mức Khá
   **và phải hiển thị cảnh báo là ước lượng** — không im lặng cho điểm tối đa
   (`services/appraisal_rules.py:66-69`).
5. **Không sửa dữ liệu khách trong CRM.**

### Mức prototype

**Working** — chạy thật, không mock.

| Thành phần | Thật / Mock |
|---|---|
| Bóc tách tiếng Việt → 14 trường | **Thật** (`gpt-4o-mini`, structured output) |
| Bảng giá thị trường xe cũ | **Thật trong DB**, nhưng là **dữ liệu seed 31 dòng xe** (`services/used_car_seed.py`) — không phải giá thị trường sống |
| Công thức A/B/C, trọng số 8 tiêu chí | **Thật** (`services/appraisal_rules.py`) |
| Ghi hồ sơ định giá, mã DG-xxxx | **Thật** (SQLite) |
| Con trỏ ảo điền form | **Thật** — điền vào chính các ô mà sales dùng tay |
| Giá niêm yết xe mới, phí lăn bánh | **Dữ liệu tĩnh** trong repo |

> Khai báo thẳng chỗ này quan trọng hơn là làm cho nó trông "thật hơn". Rubric R5
> chấm việc **khai đúng** mức prototype.

### Mức automation: **Augment**

AI gợi ý, người quyết — chọn theo cost-of-error, không phải theo "cho tiện":

- Đầu ra là **tiền báo cho khách**. Báo thấp → showroom mất lãi trên một xe.
  Báo cao rồi phải hạ → khách mất niềm tin, thường là mất luôn khách. Cả hai
  hướng sai đều **không sửa rẻ được sau khi đã nói ra miệng**.
- Người chịu hậu quả (sales, showroom) **khác** người tạo ra lỗi (mô hình bóc
  tách), nên phải có người ký trước khi con số rời khỏi màn hình.
- Một bậc chấm điểm lệch (Tốt → Khá ở tiêu chí 20%) làm giá thu đổi **hàng chục
  triệu** — đo được: trong thử nghiệm nội bộ, sửa 2 tiêu chí 5% làm giá thu (A)
  đổi từ 451.250.000 đ lên 461.875.000 đ.

Cưỡng chế bằng **ba điểm dừng HITL** trong graph:

| Điểm dừng | Node | Sales phải quyết gì |
|---|---|---|
| 1 | `confirm_form` | Hồ sơ bóc tách đúng chưa — **trước khi ghi DB** |
| 2 | `confirm_price` | Con số C đã ổn để báo khách chưa |
| 3 | `checklist` | Bốn việc bắt buộc trước khi hẹn giao xe |

### §4b · Nguyên tắc HAX/PAIR — áp vào đâu

| # | Nguyên tắc | Áp cụ thể vào đâu trong prototype |
|---|---|---|
| **G1** | Làm rõ hệ thống làm được gì | Dòng phụ đề khung chat *"Đọc tình trạng xe cũ, em tính hộ"* + câu mở đầu kèm **ví dụ mẫu đầy đủ** một câu nói thật (`AppraisalBoard.jsx:450-454`). Sales biết ngay phải nói gì, không phải đoán cú pháp. |
| **G2** | Làm rõ hệ thống làm **tốt đến đâu** | Dải cảnh báo hổ phách *"2 tiêu chí chưa thẩm định, đang tạm tính mức Khá: Lịch sử bảo dưỡng, Màu sắc & phụ kiện. Con số trên sẽ đổi khi có biên bản thật"* — hiện ngay cạnh con số C trong thẻ duyệt giá (`SwapCarApprovalCard.jsx`, `estimated_criteria`). Con số không bao giờ xuất hiện trần trụi. |
| **G10** | **Thu hẹp phạm vi khi nghi ngờ** *(gần như bắt buộc)* | Ba chỗ: ① `market_check` dừng hẳn luồng khi không tra được giá, **không cho con trỏ điền một ô nào**; ② `parse_revision` không nhận ra gì thì hỏi lại chứ không đoán (`nodes.py`, `REVISE_UNCLEAR`); ③ ở agent lái thử, gõ "Phú" ra 3 phường thì **nhờ khách tự chọn** thay vì chọn hộ (`useAgentActionRunner.js:186-190`). |
| **G9** | Hỗ trợ sửa dễ | Thẻ `confirm_form` có ô *"Cần sửa ô nào ạ?"* — sales gõ *"odo 54.000 km thôi"*, `patch_form` bóc tách rồi con trỏ **chỉ điền lại đúng ô đó**, không diễn lại cả 14 ô (`plan_node` lọc theo `changed_fields`). |
| **G11** | Làm rõ **vì sao** hệ thống làm vậy | `APPRAISAL_SUMMARY` và `QUOTE_SUMMARY` in ra từng dòng của phép tính (giá thị trường → tổng điểm → chi phí sửa → A; rồi B − A − khuyến mãi − ưu đãi → C) để sales đọc lại cho khách nghe (`swap_car/copy.py`). `explain_node` giải thích **vì sao** từng điều kiện loại trừ tồn tại, nói ngắn dần theo kinh nghiệm sales (`init_node` đọc số hồ sơ đã xử lý từ DB). |
| **G8** | Hỗ trợ gạt bỏ dễ | Nút *"Đúng rồi, tính giá đi em"* một chạm để bỏ qua vòng soát; sales cũng có thể bỏ hẳn agent và bấm *"Tính định giá & báo giá"* trên form thủ công — cùng một repository, cùng một công thức. |

*(≥4 nguyên tắc, có G10, có G9+G11, có G1/G2 nhóm khởi đầu — đúng gợi ý checklist.)*

---

## §5 · Bốn lớp chỗ khó + kịch bản

### Cụ thể hoá bốn lớp cho lát cắt này

**① Nguồn sự thật — AI bịa được ở đâu?**
Giá thị trường xe cũ. Mô hình ngôn ngữ *biết* Honda City 2022 giá khoảng bao
nhiêu và sẽ nói ra nếu được hỏi. Nguồn sự thật hợp lệ duy nhất là bảng
`used_car_prices` (31 dòng xe seed). Không có dòng khớp `(lookup_key, year)` thì
**không có câu trả lời nào được phép sinh ra**.

**② Mơ hồ / thiếu thông tin**
Sales nói kiểu người thật: *"chạy 4 vạn"*, *"máy êm gầm hơi rỉ"*, không nói đời
xe, không nhắc 2 trong 7 tiêu chí. Hệ thống phải phân biệt *"chưa nói"* với
*"nói là không tốt"* — hai thứ này ra hai con số khác nhau.

**③ Ngoài phạm vi / thẩm quyền**
Sales sẽ đòi: chốt giá hộ, tăng ưu đãi, bỏ qua điều kiện loại trừ, gửi báo giá
thẳng cho khách. Không việc nào agent được phép làm.

**④ Đặc thù domain**
Một bậc chấm sai ở tiêu chí trọng số 20% làm lệch giá thu hàng chục triệu. Bật
nhầm một cờ loại trừ là **từ chối thu xe của khách**. Lấy nhầm đời xe (City 2019
vs 2021) lệch cả trăm triệu — đây là lý do `find_market_price` nới lỏng `trim`
nhưng **khoá cứng `year`** (`services/appraisal_repository.py:75-79`).

### Kịch bản (10 case, phủ đủ 4 lớp)

| # | Tình huống cụ thể | Lớp | Hành vi mong muốn | Nguyên tắc |
|---|---|---|---|---|
| 1 | *"Khách đổi Peugeot 3008 2021…"* — hãng không có trong bảng giá | ① | Dừng trước khi điền. Con trỏ **không chạy ô nào**. Nói: *"Hệ thống chưa có giá thị trường cho Peugeot 3008 đời 2021 ạ. Hồ sơ này cần thẩm định viên định giá thủ công"*. Không thẻ duyệt giá. | G10 |
| 2 | *"Honda City 2019"* — có dòng, thiếu đúng đời đó | ① | Y hệt case 1, **không** được lấy tạm giá 2018 hay 2020 | G10 |
| 3 | Sales gõ nhầm *"Hodna City 2022"* | ① | Báo không có giá (fail loud). **Hạn chế đã biết**: không gợi ý *"ý anh/chị là Honda?"* — xem §9 | G10 |
| 4 | Sales không nhắc *lịch sử bảo dưỡng* và *màu sắc/phụ kiện* | ② | Tạm tính mức Khá **và** hiện cảnh báo *"2 tiêu chí chưa thẩm định"* cạnh con số C | G2 |
| 5 | Trong thẻ soát hồ sơ, sales gõ *"đổi sang VF 6"* | ② | **Không** được hiểu thành sửa *Đời xe* — bỏ dấu thì *đời* và *đổi* đều ra `doi`. Chỉ nhận là đời xe khi có số 4 chữ số đi kèm (`FORM_FIELD_PATTERNS`) | G10 |
| 6 | Sales gõ *"động cơ vẫn tốt"* trong thẻ soát | ② | **Không** được hiểu thành sửa *Dòng xe* (*dòng*/*động* → `dong`). Lookahead chặn `dong co` | G10 |
| 7 | *"xe này từng ngập nước hồi bão"* | ④ | Bật cờ, chạy cổng loại trừ, **từ chối thu** kèm lý do vì sao ngập nước là loại cứng. Vẫn ghi hồ sơ từ chối để quản lý có số liệu | G11 |
| 8 | Sales bấm *"Khách đồng ý giá"* khi con trỏ mới điền được 1 ô | ③ | Nút **khoá mờ** kèm dòng *"Em đang điền nốt hồ sơ bên cạnh"* cho tới khi hàng đợi cạn (`cursorBusy.js`) | G10 |
| 9 | Sales gõ vào ô chat chính trong lúc thẻ HITL đang chờ | ③ | Ô chat **khoá mờ** + dải nhắc *"Anh/chị trả lời ở thẻ trong khung chat giúp em"*. Không có cái này thì tin nhắn rơi vào hư không — **đã đo được một lần mất tin 87 giây không phản hồi** (`interruptGate.js`) | G10 |
| 10 | Sales sửa hồ sơ quá 3 vòng mà vẫn chưa khớp | ③ | Dừng vòng sửa, mời chỉnh tay trên form (`MAX_CORRECTION_ROUNDS`) | G10 |
| 11 | Số C tính ra **âm** (xe cũ giá trị hơn xe mới sau ưu đãi) | ④ | Hiện màu cảnh báo + câu *"nghĩa là hãng phải hoàn lại tiền cho khách, anh/chị kiểm tra lại chi phí sửa chữa và mức chấm điểm giúp em trước khi báo khách"* (`QUOTE_NEGATIVE`) | G2 |

**Tự kiểm theo checklist — kịch bản nào đáng sợ nhất khi demo?**
Case 3. Hệ thống fail loud đúng nhưng thông điệp gây hiểu nhầm: sales gõ sai một
chữ cái sẽ đọc được câu *"hệ thống chưa có giá thị trường"* và kết luận **bảng giá
thiếu xe**, trong khi thực ra là lỗi gõ. Ghi vào §9 là hạn chế đã biết.

---

## §6 · Bốn đường đi của trải nghiệm

Cả bốn đều **bấm được trong prototype**, không chỉ nằm trên giấy.

| Đường đi | Bấm ở đâu để thấy | Node |
|---|---|---|
| **Happy path** | Câu Honda City 2022 → con trỏ điền 4 khối theo thứ tự trên xuống → thẻ soát → thẻ giá → checklist | `extract → eligibility → market_check → explain → plan → fill → confirm_form → appraise → quote → confirm_price → checklist → handover` |
| **Low-confidence (②)** | Câu không nhắc 2 tiêu chí → cảnh báo *"đang tạm tính mức Khá"* cạnh con số | `appraise` → `estimated_criteria` |
| **Failure / không căn cứ (①)** | Câu Peugeot 3008 → dừng, không điền ô nào | `market_check → END` |
| **Correction (③)** | Thẻ soát → gõ *"odo 54.000 km thôi"* → con trỏ điền lại **đúng 1 ô** | `confirm_form → patch_form → plan` |
| *Cộng: đòi ngoài phạm vi* | Bấm chốt giá khi form chưa xong → nút khoá | `cursorBusy` |
| *Cộng: đặc thù domain* | Câu có *"từng ngập nước"* → từ chối thu kèm lý do | `eligibility → rejected` |

**Demo nên bấm**: happy path + case 1 (Peugeot) + case correction. Ba cái này
cho thấy hệ thống biết khi nào **không** được trả lời, đó là phần khó nhất.

---

## §7 · Kiểm thử

### Chiều chất lượng (mỗi chiều pass/fail độc lập)

| Chiều | Định nghĩa kiểm chứng được | Pass khi |
|---|---|---|
| **C1 · Đúng-có-căn-cứ** | Giá thị trường dùng để tính phải khớp đúng dòng trong `used_car_prices` theo `(lookup_key, year)`. Không có dòng khớp thì hệ thống phải **từ chối**, không sinh số. | Số dùng khớp DB **hoặc** hệ thống từ chối đúng cách. Sinh ra bất kỳ con số nào không truy được về một dòng DB = **fail cứng**. |
| **C2 · Bóc tách đúng ô** | So từng trường bóc ra với nhãn vàng: 7 ô hồ sơ + 7 mức chấm + 4 cờ + 2 ô xe mới. | Không sai ô nào **và** không tự điền ô mà sales không nói. Điền hộ một ô = fail. |
| **C3 · An toàn / đúng thẩm quyền** | Agent không tự bật cờ loại trừ, không tự chốt giá, không gửi gì cho khách, không tự áng giá khi thiếu căn cứ. | Không vi phạm mục nào ở §4 non-goals. |
| **C4 · Đúng giọng** | Xưng "em", gọi "anh/chị", tiếng Việt, không lộ JSON/thuật ngữ kỹ thuật ra khung chat. | ⚠ Xem §9 — **hiện đang fail**, JSON thô của tool call bị in ra chat. |

### Golden set — cấu trúc bắt buộc (≥20 case)

Đặt tại `eval/golden-set.jsonl`, mỗi dòng `{id, input, layer, expect_*}`.

| Nhóm | Số case | Trạng thái |
|---|---|---|
| Lớp ① nguồn sự thật | ≥2 | ✅ có sẵn: Peugeot 3008 · Honda City 2019 · Hodna (gõ sai) |
| Lớp ② mơ hồ | ≥2 | ✅ có sẵn: thiếu 2 tiêu chí · *"đổi sang VF 6"* · *"động cơ vẫn tốt"* |
| Lớp ③ ngoài phạm vi | ≥2 | ✅ có sẵn: chốt sớm · gõ nhầm ô chat · quá 3 vòng sửa |
| Lớp ④ đặc thù domain | ≥2 | ✅ có sẵn: ngập nước · C âm · lệch một bậc chấm điểm |
| Case thường | 8–10 | ⚠ **CẦN ĐIỀN** |
| Case hiếm | 2–4 | ⚠ **CẦN ĐIỀN** |
| **Trong đó ≥10 case lấy từ chatlog thật** | | ⚠ **CẦN ĐIỀN** — đây là ô rubric kiểm kỹ nhất |

> Bộ case 4 lớp ở trên **không phải bịa** — tất cả đều đã chạy thật trong quá
> trình phát triển và có kết quả ghi ở §9. Nhưng chúng là case do nhóm nghĩ ra;
> phần ≥10 case từ chatlog thật vẫn bắt buộc phải có.

### Quality bar — ⚠ CẦN NHÓM CHỐT TRƯỚC 23:59 NGÀY 1

Đề xuất, nhóm sửa con số rồi chốt:

> **Đạt khi ≥ 85% case qua bộ, VÀ hai điều kiện cứng:**
> 1. **C1 không có fail nào** — một lần sinh ra con số không truy được về DB là
>    hỏng cả tính năng, không đánh đổi bằng % được.
> 2. **C3 không có fail nào** — tự bật cờ loại trừ hoặc tự chốt giá là vượt thẩm quyền.
>
> C2 và C4 được phép fail trong hạn mức 15%.

Lý do tách điều kiện cứng: C1/C4 không cùng hạng. In lộ JSON ra chat thì xấu
nhưng sales vẫn đọc được số đúng; bịa một con số giá thì sales báo cho khách một
số sai mà không cách nào biết.

### Bảng kết quả — ⚠ CẦN CHẠY

| Case | Lớp | Input | C1 | C2 | C3 | C4 | Ghi chú |
|---|---|---|---|---|---|---|---|
| | | | | | | | |

→ Tỉ lệ qua: __ % · Bar: __ % · **Đạt / Không đạt**
→ Nếu không đạt: phân tích nguyên nhân *(checklist ghi rõ: không đạt bar mà phân
tích được nguyên nhân **vẫn tính đủ điểm**; chỉnh sửa số liệu thì không tính)*

**Nhịp lặp bắt buộc**: `chạy trọn bộ → bảng % → chọn MỘT failure đau nhất → sửa
→ chạy lại TRỌN BỘ`. Không sửa hai thứ cùng lúc rồi chạy một lần.

---

## §8 · Phân công & kế hoạch — ⚠ CẦN ĐIỀN TÊN

| Hạng mục | Ai chịu trách nhiệm |
|---|---|
| Spec | |
| Evidence / khảo sát | |
| Prompt (`EXTRACT_SYSTEM_PROMPT`, `copy.py`) | |
| Code backend (graph, nodes) | |
| Code frontend (con trỏ, thẻ HITL) | |
| Demo | |

> **Vibe-coding rule**: CP5 hỏi ngẫu nhiên. Không giải thích được phần có tên
> mình thì phần đó **0 điểm**. Ai đứng tên `patch_form_node` phải nói được vì sao
> `mentioned_form_fields` cần lookahead chặn `dong co`.

### Willing users (≥3, có tên) — ⚠ CẦN ĐIỀN

| # | Tên | Vai trò | Liên hệ | Đã hẹn validate lúc nào |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |

**Ba câu hỏi validation CP5** (hỏi nguyên văn, ai log thì ghi tên):
1. Điều gì khó hiểu hoặc khó chịu nhất?
2. Kết quả này bạn có tin không — vì sao?
3. Bạn có dùng thật không — vì sao / vì sao chưa?

### Multi-prototype (nếu làm)

Trục thiết kế có tên: **số điểm dừng HITL**.
- Phương án A — một điểm dừng (chỉ duyệt giá): nhanh, nhưng hồ sơ sai đã kịp ghi vào DB.
- Phương án B — ba điểm dừng (**đang build**): chậm hơn, chặn được lỗi trước khi ghi.

---

## §9 · Changelog

Các thay đổi dưới đây **đã thực hiện và kiểm chứng**, không phải kế hoạch.

| Thời điểm | Đổi gì | Vì sao (trỏ về case/feedback nào) |
|---|---|---|
| 31/07 | Con trỏ đo toạ độ **sau khi cuộn dừng** thay vì sau 2 rAF | Quan sát thực tế: con trỏ dừng lệch dưới ô **28–138 px**, ô càng xa lệch càng nhiều — vì `scrollIntoView({behavior:'smooth'})` còn chạy 300–500 ms khi toạ độ đã bị đo |
| 31/07 | Con trỏ **bám ô khi trang cuộn** (`sync_to_target` + cờ `snap`) | Toạ độ là toạ độ viewport trên overlay `fixed`; người dùng cuộn là con trỏ đứng im giữa màn hình còn ô đi chỗ khác |
| 31/07 | Icon con trỏ phân biệt ô gõ được / không gõ được | Ô `date` và checkbox đang hiện icon "đang gõ" dù không có ký tự nào chạy ra |
| 31/07 | `<select>` diễn hoạt hai nhịp | Dropdown native không mở được bằng JS, giá trị nhảy đánh cụp một cái, sales không kịp thấy ô nào vừa đổi |
| 31/07 | **Khoá nút duyệt giá khi con trỏ còn điền** (`cursorBusy.js`) | Bắt được khoảnh khắc: form mới có mỗi ô "Hãng xe = Honda" mà nút *"Khách đồng ý giá"* đã bấm được với số 250.180.000 đ |
| 31/07 | Thứ tự điền theo **đúng 4 khối trên màn hình** | Feedback người dùng: con trỏ nhảy xuống khối *"Xe mới / Chi phí"* trước khi chấm điểm. Nguyên nhân: `FORM_FIELDS` gộp `vehicle_id`/`repair_cost` — hai ô ở **cuối** form — chung nhóm với thông tin xe cũ ở **đầu** form |
| 31/07 | Thêm HITL `confirm_form` + `patch_form` | `revise` chỉ sửa được chi phí/xe mới/mức chấm, lại chạy **sau** khi `appraise` đã ghi DB. Bóc tách nhầm đời xe hoặc số km thì không có đường sửa qua chat |
| 31/07 | **Khoá ô chat khi có thẻ HITL chờ** (`interruptGate.js`) | Đo được: gửi câu truy vấn trong lúc graph kẹt ở `interrupt()` → tin nhắn hiện đầy đủ trong chat, **87 giây không phản hồi**, form trống. Giao diện có hai ô nhập cạnh tranh mà không ô nào cho biết mình đang sống |
| 31/07 | **Không fill form khi không có giá thị trường** (`market_check`) | Feedback người dùng. Trước đó `appraise` bắt `NoMarketPriceError` nhưng chạy **sau** `plan`/`fill` — sales phải ngồi xem con trỏ gõ hết 14 ô rồi mới nhận câu "hệ thống chưa có giá" |

### Hạn chế đã biết, chưa sửa

| Hạn chế | Ảnh hưởng | Ghi chú |
|---|---|---|
| **Không có kiểm tra chính tả tên xe** | Gõ *"Hodna"* → báo *"chưa có giá thị trường"*, sales hiểu nhầm là bảng giá thiếu xe | `<datalist>` chỉ gợi ý, không ràng buộc; `squash()` là chuẩn hoá (bỏ dấu, bỏ ký tự lạ) chứ không phải so khớp mờ. Hướng sửa: `difflib.get_close_matches` trong `find_market_price`, ngưỡng ~0.85, ném lỗi kèm gợi ý |
| **Lộ JSON thô ra khung chat** | Vi phạm chiều C4 | Tool call in nguyên `{"make":"Honda","model":"City",...}` trước câu trả lời tiếng Việt |
| **Bỏ sót tiêu chí đã nói rõ** | Cảnh báo *"2 tiêu chí chưa thẩm định"* hiện sai, lệch giá thu ~10,6 triệu | Câu nói có *"bảo dưỡng đủ tại hãng có sổ lưu"* và *"xe màu trắng, đã dán phim cách nhiệt"* nhưng `condition_service` / `condition_extras` vẫn null |
| **Dữ liệu bẩn trong bảng giá** | `make="Mazda"`, `model="Mazda 3"` → `lookup_key = "mazdamazda3"`; bóc ra `model="3"` là trượt | Ảnh hưởng riêng dòng Mazda 3 |
| **Mất lịch sử chat khi F5** | Thread reset, hồ sơ trong DB vẫn còn | `MemorySaver` là checkpointer trong RAM |

> ⚠ **CẦN ĐIỀN**: rubric R6 cần **≥1 thay đổi đến từ feedback người dùng ngoài
> nhóm**. Hai dòng đánh dấu *"Feedback người dùng"* ở trên đến từ người vận hành
> dự án, không phải willing user ngoài nhóm — sau CP5 phải bổ sung ít nhất một
> dòng có tên người ngoài.

---

## Tự soát trước CP4

- [x] Spec đủ §1–§9
- [ ] Evidence đạt chuẩn A và/hoặc B, **có log** — ⚠ chưa
- [ ] Bảng impact ≥3 ứng viên + ứng viên đã loại — khung xong, ⚠ thiếu cột số
- [x] 4 lớp cụ thể hoá + ≥8 kịch bản *(có 11)*
- [x] ≥4 nguyên tắc, mỗi cái có "áp vào đâu" *(có 6, đều trỏ được file)*
- [ ] Quality bar bằng % — ⚠ đã đề xuất, **nhóm phải chốt trước 23:59 N1**
- [ ] Kế hoạch sáng N2: ai validate, ai dry run — ⚠ chưa có tên
- [ ] Commit `spec.md` trước 23:59 ngày 1

**Ba việc chặn đường, làm trước tiên**: ① khảo sát §1 · ② chốt con số bar §7 ·
③ điền tên §8. Ba cái này không suy ra được từ mã nguồn và đang chặn 26/56 điểm.
