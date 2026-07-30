# PROMPT: Thêm tính năng "Thêm khách" trong CRM + AI Copilot hỗ trợ sales nhập lead

> Prompt này mở rộng dự án "VinFast Electric Showcase + AI Copilot" hiện có
> (xem `REBUILD_PROMPT.md` để hiểu nền tảng). KHÔNG viết lại từ đầu — tái sử dụng
> tối đa hạ tầng agent/cursor/form đã chạy. Toàn bộ UI và thông báo bằng tiếng Việt.
> Quy ước frontend: snake_case cho biến/hàm/props. Chạy `ruff check` + `pytest` xanh
> trước khi kết thúc.

---

## 1. Bối cảnh & mục tiêu

Hiện tại lead chỉ vào hệ thống qua form trên trang khách (`/`). Nhân viên kinh doanh
(sales) gặp khách qua điện thoại/showroom/Zalo thì chưa có chỗ nhập. Cần bổ sung vào
Admin Portal (`/admin-portal`, component `AdminPortal.jsx`) một luồng **sales tự tạo
lead**, có AI Copilot điền form hộ giống hệt trải nghiệm trên trang khách:

1. Nút **"Thêm khách"** đặt **bên trái** nút "Tải lại" trên header dashboard.
2. Bấm vào mở **AddCustomerModal**: form cùng bộ trường với form lái thử của khách,
   kèm **khung chat CopilotKit nhúng ngay trong modal**. Sales vừa nghe khách nói
   chuyện vừa nhắn cho agent ("Khách tên Trần Văn A, 0987654321, muốn lái thử VF 8
   sáng mai ở Hoàn Kiếm"), agent bóc thông tin, **con trỏ ảo điền từng ô**, tóm tắt,
   **human-in-the-loop 2 bước** (xác nhận thông tin → xin phép submit) y như luồng khách.
3. **Kiểm tra trùng**: SĐT trùng = chặn cứng (không cho tạo); họ tên trùng = cảnh báo
   mềm (vẫn cho submit).
4. Submit thành công → hiện **mã đăng ký `VF-xxxxx`** + NVKD được phân công cho sales,
   danh sách khách trên dashboard tự tải lại.

---

## 2. Cấu trúc thư mục backend — tái tổ chức `agents/` thành n thư mục cho n agent

Hiện tại `src/backend/agents/` phẳng và chỉ phục vụ một agent. Việc đầu tiên của
prompt này là **tách thành `shared/` + một thư mục cho mỗi agent**, để về sau thêm
agent thứ 3, thứ 4 (đổi xe, trả góp — xem `agent-crm-flow.md`) không phải sửa lại
cấu trúc nữa.

### 2.1 Trước và sau

```
TRƯỚC (phẳng, 1 agent)              SAU (shared + n thư mục agent)
────────────────────────            ─────────────────────────────────────────────
agents/                             agents/
├── graph.py         (facade)       ├── __init__.py
├── form_graph.py    (wiring)       ├── shared/                 ← DÙNG CHUNG
├── state.py                        │   ├── __init__.py
├── catalog.py                      │   ├── state.py            ← AgentState + FORM_FIELDS
├── wards.py                        │   ├── catalog.py          ← match_vehicle/match_ward/...
└── nodes/                          │   ├── wards.py            ← HANOI_WARDS (127 phường)
    └── form_nodes.py  828 dòng     │   ├── copy.py             ← MỚI: resolver câu chữ
                                    │   └── nodes/
                                    │       ├── __init__.py
                                    │       └── form_nodes.py   ← 828 dòng GIỮ NGUYÊN CHỖ NÀY
                                    ├── test_drive/             ← AGENT 1 (khách tự đăng ký)
                                    │   ├── __init__.py
                                    │   ├── copy.py             ← câu chữ nói VỚI KHÁCH
                                    │   └── graph.py            ← build_graph() + agent
                                    └── crm_lead/               ← AGENT 2 (sales nhập hộ)
                                        ├── __init__.py
                                        ├── copy.py             ← câu chữ nói VỚI SALES
                                        ├── nodes.py            ← node riêng: check trùng SĐT
                                        └── graph.py            ← build_graph() + agent
```

**Nguyên tắc chia — bắt buộc tuân thủ khi thêm agent mới về sau:**

| Thứ gì | Đặt ở đâu | Lý do |
|---|---|---|
| `AgentState`, `FORM_FIELDS`, `REQUIRED_FIELDS`, `FIELD_LABELS` | `shared/state.py` | Cả 2 agent điền cùng bộ 8 field |
| Chuẩn hoá dữ liệu, tra xe/phường (`catalog.py`, `wards.py`) | `shared/` | Không phụ thuộc agent nào |
| 12 node + 5 router điền form (`form_nodes.py`) | `shared/nodes/` | **~90% logic trùng nhau — cấm copy sang thư mục agent** |
| Câu chữ agent nói ra | `<agent>/copy.py` | Chỗ khác biệt thật giữa 2 agent |
| Lắp graph, đặt tên agent | `<agent>/graph.py` | Mỗi agent một topology riêng |
| Node chỉ agent đó có | `<agent>/nodes.py` | Ví dụ check trùng SĐT chỉ CRM cần |

> Điểm mấu chốt: **`form_nodes.py` KHÔNG được nhân bản.** Đó là nơi chứa toàn bộ
> phần khó (`_normalize_date`, `_snap_time`, `direct_captures`, `mentioned_fields`,
> chống lặp theo `run_seq`). Fork nó ra 2 bản là bảo đảm sau vài ngày hai bên lệch
> nhau và bug chỉ được sửa ở một bên.

### 2.2 `shared/copy.py` — tách câu chữ khỏi logic

Định nghĩa một dataclass `CopyPack` gom mọi câu agent phát ra (greeting, ask_missing
prefix, summary header, confirm_details, confirm_submit, report thành công, thông báo
lỗi LLM...) và một resolver:

```python
def get_copy(state) -> CopyPack:
    # Import TRONG hàm là có chủ đích: agents/<agent>/copy.py import CopyPack từ
    # shared/, nên import ở module level sẽ tạo vòng tròn.
    if (state.get("channel") or "web") == "crm":
        from ..crm_lead.copy import COPY
    else:
        from ..test_drive.copy import COPY
    return COPY
```

Node trong `shared/nodes/form_nodes.py` thay chuỗi hardcode bằng `get_copy(state).xxx`.
Ví dụ `extract_node` hiện hardcode `"Chào anh/chị! Anh/chị muốn lái thử mẫu xe nào..."`
→ bản CRM là `"Anh/chị đọc thông tin khách giúp em: tên, SĐT, mẫu xe, ngày giờ, khu vực."`

### 2.3 `channel` do graph tự đóng dấu, KHÔNG để frontend set

`shared/state.py` thêm field top-level `channel: Literal["web", "crm"]`. Mỗi
`<agent>/graph.py` mở đầu bằng một node `init` cực nhỏ ghi `channel` của mình:

```python
def make_init_node(channel: str):
    async def init_node(state):  # noqa: ARG001
        return {"channel": channel}
    return init_node
```

`START → init → extract → ...` cho cả 2 agent. Làm vậy vì nếu trông vào frontend
`setState` thì chỉ cần một lần quên là agent CRM nói giọng dành cho khách.

Riêng `source` (Showroom/Facebook/Zalo/Website) **thì ngược lại** — sales chọn được
trên form nên vẫn để frontend `setState`. Cả `channel` và `source` đều là field
top-level, **KHÔNG cho vào `draft`/`FORM_FIELDS`**, kẻo `plan_node` sinh action đi
điền một ô không tồn tại.

### 2.4 Topology 2 graph

`test_drive/graph.py` — giữ đúng luồng cũ, chỉ thêm node `init`:

```
START → init → extract → ask_missing → END
                       → plan → fill* → summarize → confirm_details
                         confirm_details → patch → plan | ask_submit → confirm_submit
                         confirm_submit → submit → report → END | manual_ready → END
```

`crm_lead/graph.py` — **giống hệt, chèn thêm 1 node `check_duplicate`** giữa
`summarize` và `confirm_details`:

```
... → summarize → check_duplicate ─┬─ (trùng SĐT)  → duplicate_blocked → END
                                   └─ (sạch/trùng tên) → confirm_details → ...
```

Tách thành node riêng trong `crm_lead/nodes.py` thay vì nhét `if` vào
`summarize_node` dùng chung — nhờ vậy graph khách hàng không phải gánh nhánh mình
không dùng, và test 2 luồng độc lập được.

### 2.5 Việc phải làm khi di chuyển file (blast radius)

Đây là refactor thuần, `git mv` là xong phần lớn, nhưng **phải sửa import ở đúng 6 chỗ**:

| File | Sửa gì |
|---|---|
| `src/backend/main.py` | `from .agents.graph import form_agent` → import `agent` từ **cả 2** `agents/test_drive/graph.py` và `agents/crm_lead/graph.py` |
| `src/backend/agents/shared/nodes/form_nodes.py` | `from ..catalog import ...` và `from ..state import ...` vẫn đúng độ sâu; thêm `from ..copy import get_copy` |
| `tests/test_agents/conftest.py:5` | → `src.backend.agents.shared.nodes.form_nodes` |
| `tests/test_agents/test_form_nodes.py:7,25` | → `...shared.nodes.form_nodes`, `...shared.state` |
| `tests/test_agents/test_catalog.py:13,20` | → `...shared.catalog`, `...shared.wards` |
| `src/backend/Dockerfile` | không cần sửa — đã `COPY src/backend ./src/backend` cả cây |

Xoá `agents/graph.py` và `agents/form_graph.py` sau khi nội dung đã chuyển sang
`test_drive/graph.py`. **Đừng quên `__init__.py` rỗng ở `shared/`, `shared/nodes/`,
`test_drive/`, `crm_lead/`** — thiếu là import vỡ trong container.

Cấu trúc test đi theo cấu trúc source:

```
tests/test_agents/
├── conftest.py            ← mock LLM, dùng chung
├── test_catalog.py        ← giữ nguyên nội dung, chỉ đổi import
├── test_form_nodes.py     ← giữ nguyên: test node dùng chung
└── test_crm_lead.py       ← MỚI: check_duplicate, copy CRM, source, submit trùng
```

---

## 3. Quyết định kiến trúc còn lại

- **Phơi 2 endpoint AG-UI** trong `_mount_agent_endpoint` của `main.py`:
  `LangGraphAgent(name="test_drive_agent", graph=test_drive_agent_graph)` tại
  `/agent/test-drive`, và `LangGraphAgent(name="crm_lead_agent", graph=crm_lead_graph)`
  tại `/agent/crm-lead`. nginx đã proxy prefix `/agent/` với `proxy_buffering off`
  nên **không cần sửa nginx**.
- **Chọn agent theo trang** trong `main.jsx`: tạo 2 `HttpAgent` (URL CRM đọc từ
  `VITE_CRM_AGENT_URL`, mặc định `"/agent/crm-lead"` — nhớ thêm build arg vào
  `src/frontend/Dockerfile` + `docker-compose.yml`), đăng ký cả hai vào
  `agents__unsafe_dev_only`, còn prop `agent` chọn theo
  `window.location.pathname === '/admin-portal'`. Hai trang là 2 lần full page load
  riêng nên không bao giờ mount đồng thời.
- **Một đường ghi duy nhất**: check trùng SĐT ở tầng chặn cuối đặt trong
  `customer_repository.create_test_drive` để phủ cả 3 đường (form khách, form CRM,
  agent submit). Ghi rõ chủ đích này trong docstring.
- Tên agent phải khớp **chính xác 3 nơi**: `LangGraphAgent(name=...)`, key trong
  `agents__unsafe_dev_only`, và `useCoAgent({name:...})`. Lệch 1 ký tự thì chat im
  lặng, không báo lỗi.

---

## 4. Backend

### 4.1 Kiểm tra trùng — `services/customer_repository.py`

- `normalize_phone(value) -> str`: giữ lại chữ số. `normalize_name(value) -> str`:
  casefold, gộp khoảng trắng, **bỏ dấu tiếng Việt** (NFD + loại combining marks —
  "Trần Văn Tuấn" phải khớp "Tran Van Tuan").
- `find_duplicates(session, *, phone, name) -> tuple[Customer | None, list[Customer]]`:
  - `phone_match`: khách đầu tiên có SĐT chuẩn hoá **trùng tuyệt đối** (SĐT trong DB
    đã được validator chuẩn hoá thành chuỗi số sẵn).
  - `name_matches`: mọi khách có tên chuẩn hoá trùng (so trong Python sau khi query —
    SQLite không bỏ dấu được; dữ liệu demo nhỏ, chấp nhận full scan).
- `class DuplicatePhoneError(Exception)` mang theo `customer` bị trùng.
  `create_test_drive` gọi `find_duplicates` trước khi ghi; trùng SĐT → raise.

### 4.2 API — `api/routes.py`, `models/schemas.py`

- `GET /api/v1/customers/check-duplicate?phone=...&name=...` (cả 2 optional)
  → `DuplicateCheckOut { phone_match: CustomerOut | None, name_matches: list[CustomerOut] }`.
  **Khai báo route này TRƯỚC các route `/customers/{code}/...`** để không bị nuốt path.
- `POST /test-drives`: bắt `DuplicatePhoneError` → **409**, detail:
  `"Số điện thoại đã đăng ký cho khách {code} — {name}. Vui lòng kiểm tra lại."`
- Trùng tên KHÔNG BAO GIỜ chặn ở backend.

### 4.3 Agent

**`shared/state.py`**: thêm `channel: Literal["web","crm"]` và `source: str`, cập nhật
`empty_state()`.

**`shared/nodes/form_nodes.py`**: thay câu chữ hardcode bằng `get_copy(state)`;
`submit_node` đọc `state.get("source") or "Website"` thay cho `source="Website"` đang
hardcode; `submit_node` bắt `DuplicatePhoneError` (chốt chặn cuối, chống race giữa 2
sales) → trả message tiếng Việt kèm mã khách cũ, `status="duplicate_phone"`, không
làm sập graph.

**`crm_lead/nodes.py`**:
- `check_duplicate_node`: gọi `find_duplicates` bằng SĐT trong draft.
  - Trùng SĐT → `status="duplicate_phone"`, message:
    `"Số điện thoại này đã có trong hệ thống với mã {code} ({name}). Anh/chị kiểm tra
    lại — nếu đúng là khách khác, sửa lại số điện thoại giúp em."`
  - Chỉ trùng tên → đi tiếp `confirm_details`, nối thêm vào summary:
    `"⚠ Lưu ý: đã có khách trùng tên ({code}), khác số điện thoại — vẫn tạo mới được."`
- `route_after_check_duplicate` → `"duplicate_blocked"` | `"confirm_details"`.
- `duplicate_blocked_node` → END. Lượt chat sau với SĐT mới chạy lại từ `extract`
  bình thường (`TERMINAL_STATUSES` đã lo phần reset draft — thêm
  `"duplicate_phone"` vào set đó).

---

## 5. Frontend

### 5.1 Nút "Thêm khách" — `AdminPortal.jsx`

Trong header của `Dashboard`, thêm nút trước nút "Tải lại" (icon `UserPlus` của
lucide-react, style `btn-primary`): `[+ Thêm khách] [Tải lại] [Đăng xuất(mobile)]`.

### 5.2 `AddCustomerModal.jsx` (component mới)

- Layout 2 khối: **trái = form**, **phải = khung chat `CopilotChat`**
  (`@copilotkit/react-ui`, nhúng thẳng — KHÔNG dùng `CopilotPopup` ở trang admin).
  Mobile: chat xếp dưới form.
- Form: đúng bộ trường của `TestDriveModal` (họ tên*, SĐT*, email, mẫu xe* select,
  ngày* min=hôm nay, giờ* 6 khung, tỉnh readonly "Hà Nội", `WardSelect`*, ghi chú)
  **cộng thêm** select **"Nguồn"**: `Showroom` (mặc định) / `Facebook` / `Zalo` /
  `Website` — đúng tuple `SOURCES` backend. Nếu tách được phần fields của
  `TestDriveModal` ra dùng chung thì tách; nếu quá xâm lấn thì chấp nhận lặp, nhưng
  **bắt buộc giữ nguyên `data-agent-field`, `data-agent-ward-search`,
  `data-agent-ward-option` và contract ref của WardSelect** — đó là thứ khiến action
  runner cũ chạy được trên form mới mà không sửa dòng nào.
- **Nâng state form lên `Dashboard`** (bài học cũ: agent điền xong mà modal unmount
  là mất sạch). Dashboard nắm: `form_data`, `selected_vehicle_id`, `ward_notice`,
  `modal_open`, `animation_idle`, `ward_select_ref` — sao chép đúng pattern wiring
  trong `App.jsx` (Showcase): `useCoAgent({name:'crm_lead_agent', ...})`,
  `useAgentCursor`, `useAgentActionRunner`, reset theo `run_seq`/`run_kind`, tự mở
  modal khi `status==='filling'`.
- **HITL**: `useLangGraphInterrupt` render `AgentApprovalCard` (tái sử dụng nguyên
  component) — thẻ xác nhận hiện trong khung chat của modal. Vì chat nhúng trong
  modal, **cấm đóng modal khi graph đang chờ interrupt** (đang `awaiting`): nút X
  disabled kèm tooltip "Hãy trả lời thẻ xác nhận trong khung chat trước".
- Select "Nguồn" đổi → `setState` của `useCoAgent` ghi `source` top-level.

### 5.3 Kiểm tra trùng phía UI

- `api.js` thêm `check_duplicate({phone, name})`.
- SĐT: debounce 400ms khi đủ ≥10 số → gọi API. Trùng → viền đỏ + dòng lỗi
  `"Trùng SĐT với khách {code} — {name}"` + **disable nút submit**.
- Họ tên: debounce tương tự → trùng thì cảnh báo **vàng** (amber):
  `"Đã có khách trùng tên ({code}) — vẫn có thể tạo mới."` — KHÔNG chặn submit.
- Submit vẫn phải xử lý **409** từ backend (lọt lưới/race): hiện detail ngay dưới nút.

### 5.4 Sau khi submit (yêu cầu 4)

Màn hình thành công trong modal (cả submit tay lẫn agent submit qua `submission_code`
trong agent state): mã **`VF-xxxxx`** cỡ lớn + tên khách + lịch hẹn + **NVKD được phân
công** (từ `CustomerOut.sales_staff`) + 2 nút: `"Thêm khách khác"` (reset form + state
submitted, giữ modal) và `"Đóng"`. Ngay khi có kết quả → gọi `load()` của Dashboard để
khách mới nằm đầu bảng với badge "Mới" và đúng cột Nguồn.

---

## 6. Bẫy phải né (thiếu là hỏng)

| # | Bẫy | Hậu quả nếu bỏ qua |
|---|---|---|
| 1 | Không nhân bản `form_nodes.py` sang thư mục agent | 2 bản lệch nhau, bug chỉ được sửa 1 bên |
| 2 | `__init__.py` rỗng ở cả 4 thư mục mới | import vỡ trong container Linux |
| 3 | `get_copy` import copy pack **trong hàm** | circular import: `crm_lead/copy.py` cần `CopyPack` từ `shared/` |
| 4 | `channel` do node `init` của graph ghi, không nhờ frontend | quên set 1 lần là agent CRM nói giọng dành cho khách |
| 5 | `channel`/`source` là field top-level, không nằm trong `FORM_FIELDS` | `plan_node` sinh action điền ô không tồn tại |
| 6 | `data-agent-field` trên form CRM trùng TÊN với form khách | action runner không tìm thấy ô, con trỏ đứng im |
| 7 | `controls` của cursor bọc `useMemo`, copy đúng pattern `App.jsx` | effect chạy lại giữa animation, điền nửa chừng rồi dừng |
| 8 | Route `check-duplicate` khai báo trước `/customers/{code}/status` | FastAPI match nhầm `{code}="check-duplicate"` → 404/422 khó hiểu |
| 9 | Chặn đóng modal khi đang chờ interrupt | graph treo vĩnh viễn ở `interrupt()`, sales phải F5 |
| 10 | `submit_node` vẫn bắt `DuplicatePhoneError` dù đã có `check_duplicate` | 2 sales nhập cùng lúc → exception xé graph giữa chừng |
| 11 | Thêm `"duplicate_phone"` vào `TERMINAL_STATUSES` | lượt sau không reset draft, dữ liệu khách cũ rò sang khách mới |
| 12 | Build arg `VITE_CRM_AGENT_URL` khai ở cả Dockerfile lẫn compose | bản docker trỏ agent CRM về localhost:8000 → chết trong container |

---

## 7. Kiểm thử & nghiệm thu

**Refactor trước, tính năng sau:** bước 1 chỉ di chuyển file + sửa import, **`pytest`
phải xanh nguyên 143 test trước khi viết dòng tính năng đầu tiên**. Đó là lưới an toàn
duy nhất chứng minh việc tách thư mục không làm hỏng gì.

**Tests mới (mock LLM như bộ test hiện có):**
1. `find_duplicates`: trùng SĐT khác định dạng nhập ("0987 654 321" vs "0987654321"),
   trùng tên khác dấu/hoa thường, không trùng.
2. API: POST trùng SĐT → **409** kèm mã khách cũ; trùng tên → **201**;
   `check-duplicate` trả đúng cả 2 nhánh; route `{code}` cũ không vỡ.
3. `test_crm_lead.py`: `check_duplicate_node` chặn đúng và message chứa mã khách cũ;
   trùng tên thì đi tiếp confirm_details kèm dòng cảnh báo; `submit_node` nuốt
   `DuplicatePhoneError` êm; graph CRM sinh `channel="crm"` và dùng copy CRM;
   graph khách vẫn ra `channel="web"` + `source="Website"`.

**Kịch bản nghiệm thu end-to-end:**
Đăng nhập `/admin-portal` → "Thêm khách" → nhắn *"Khách tên Trần Văn A, 0987654321,
lái thử VF 8 lúc 9 rưỡi sáng mai ở Hoàn Kiếm, khách đến showroom"* → con trỏ điền
từng ô, tóm tắt, thẻ xác nhận 2 bước → "Tự động gửi" → hiện mã VF-xxxxx + NVKD, bảng
có dòng mới nguồn "Showroom". Bấm "Thêm khách khác", nhập lại đúng SĐT 0987654321 →
agent báo trùng kèm mã cũ, không tạo; gõ tay SĐT đó vào form → ô đỏ, nút submit
disable. Nhập khách "Trần Văn A" khác với SĐT khác → chỉ cảnh báo vàng, submit thành
công. Cuối cùng mở lại trang khách `/` và chạy 1 lượt đăng ký → phải hoạt động y như
trước, `source="Website"`.
