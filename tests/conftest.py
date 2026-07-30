"""Cấu hình môi trường test.

Phải đặt biến môi trường TRƯỚC khi bất kỳ module nào của backend được import,
vì `services/database.py` tạo engine ngay lúc import theo `get_settings()`.
pytest nạp conftest.py trước test module nên chỗ này là đúng thời điểm.
"""

import os
import tempfile
from pathlib import Path

_tmp_dir = Path(tempfile.mkdtemp(prefix="vinfast_test_"))

os.environ["DATABASE_URL"] = f"sqlite:///{(_tmp_dir / 'test.db').as_posix()}"
os.environ["OPENAI_API_KEY"] = "sk-test-not-used"
os.environ["MODEL_NAME"] = "gpt-4o-mini"
os.environ["LLM_TEMPERATURE"] = "0"
os.environ["CORS_ORIGINS"] = "http://localhost:5173"
