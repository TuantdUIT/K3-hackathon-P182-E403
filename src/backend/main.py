"""Ứng dụng FastAPI: REST API + endpoint AG-UI cho agent."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .agents.graph import form_agent
from .api.routes import router
from .config import get_settings
from .services.database import init_db

logger = logging.getLogger(__name__)

# Dịch thông báo lỗi mặc định của pydantic/FastAPI sang tiếng Việt.
# Toàn bộ UI là tiếng Việt nên không thể để lọt "Field required" ra màn hình.
VALIDATION_MESSAGES: dict[str, str] = {
    "Field required": "Trường này là bắt buộc.",
    "Input should be a valid date": "Ngày không đúng định dạng (YYYY-MM-DD).",
    "Input should be a valid date or datetime, input is too short": "Ngày không đúng định dạng (YYYY-MM-DD).",
    "Input should be a valid string": "Giá trị phải là chuỗi ký tự.",
    "Input should be a valid integer": "Giá trị phải là số nguyên.",
    "Input should be a valid boolean": "Giá trị phải là true hoặc false.",
    "Input should be a valid dictionary or instance": "Dữ liệu gửi lên không đúng cấu trúc.",
    "String should have at least 2 characters": "Cần ít nhất 2 ký tự.",
    "String should have at least 1 character": "Không được để trống.",
}

FIELD_LABELS_VI: dict[str, str] = {
    "name": "Họ và tên",
    "phone": "Số điện thoại",
    "email": "Email",
    "vehicle_id": "Mẫu xe",
    "model": "Mẫu xe",
    "test_drive_date": "Ngày lái thử",
    "test_drive_time": "Giờ lái thử",
    "province": "Tỉnh/Thành phố",
    "ward": "Phường/Xã",
    "note": "Yêu cầu khác",
    "status": "Trạng thái",
    "source": "Nguồn",
    "email_address": "Email",
    "password": "Mật khẩu",
}


def translate_validation_message(message: str) -> str:
    if message in VALIDATION_MESSAGES:
        return VALIDATION_MESSAGES[message]

    # Lỗi từ field_validator đi kèm tiền tố "Value error, " — bỏ tiền tố là ra
    # đúng câu tiếng Việt mình đã viết trong schema.
    if message.startswith("Value error, "):
        return message[len("Value error, ") :]

    for prefix, translated in VALIDATION_MESSAGES.items():
        if message.startswith(prefix):
            return translated

    return message


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="VinFast Electric Showcase API",
        description="API cho trang showcase xe điện, Admin Portal và AI Copilot điền form lái thử.",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(  # noqa: ARG001
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = []
        for error in exc.errors():
            location = [str(part) for part in error.get("loc", []) if part != "body"]
            field = location[-1] if location else ""
            errors.append(
                {
                    "field": field,
                    "label": FIELD_LABELS_VI.get(field, field),
                    "message": translate_validation_message(str(error.get("msg", ""))),
                }
            )

        summary = "; ".join(
            f"{item['label']}: {item['message']}" if item["label"] else item["message"]
            for item in errors
        )
        return JSONResponse(
            status_code=422,
            content={"detail": summary or "Dữ liệu gửi lên không hợp lệ.", "errors": errors},
        )

    app.include_router(router)

    @app.get("/health")
    def health() -> dict[str, str]:
        """Healthcheck của docker-compose gọi đúng đường dẫn này."""
        return {"status": "ok"}

    _mount_agent_endpoint(app)
    return app


def _mount_agent_endpoint(app: FastAPI) -> None:
    """Phơi graph theo giao thức AG-UI.

    BẪY #2 — nối THẲNG AG-UI, KHÔNG dùng `CopilotKitRemoteEndpoint`.
    `CopilotKitRemoteEndpoint` nói giao thức remote-endpoint v1, cần thêm một
    CopilotKit Runtime chạy trên Node đứng giữa. Còn `@copilotkit/react-core`
    1.63 trên trình duyệt nói v2 và tự đọc được AG-UI. Cắm trực tiếp thì bỏ hẳn
    được tiến trình Node trung gian, và mọi state-delta của graph ra tới
    frontend nguyên vẹn.
    """
    try:
        from ag_ui_langgraph import LangGraphAgent, add_langgraph_fastapi_endpoint
    except ImportError:  # pragma: no cover
        logger.warning(
            "Chưa cài ag-ui-langgraph nên bỏ qua endpoint /agent/test-drive. "
            "Chạy: pip install -r requirements.txt"
        )
        return

    add_langgraph_fastapi_endpoint(
        app,
        LangGraphAgent(name="test_drive_agent", graph=form_agent),
        "/agent/test-drive",
    )


app = create_app()
