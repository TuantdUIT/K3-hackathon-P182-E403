"""Sinh lại `src/backend/agents/wards.py` từ `src/frontend/src/data/hanoi_wards.js`.

File JS là nguồn sự thật. Chạy script này mỗi khi sửa danh mục phường/xã:

    python scripts/sync_wards.py

`tests/test_agents/test_catalog.py` sẽ fail nếu hai bên lệch nhau.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS_FILE = ROOT / "src" / "frontend" / "src" / "data" / "hanoi_wards.js"
PY_FILE = ROOT / "src" / "backend" / "agents" / "wards.py"

WARD_LINE = re.compile(r"^\s*'([^']+)',\s*$", re.MULTILINE)

HEADER = '''"""Danh mục 127 phường/xã Hà Nội.

TỰ SINH — đừng sửa tay. Nguồn sự thật là
`src/frontend/src/data/hanoi_wards.js`; chạy `python scripts/sync_wards.py`
để cập nhật file này.
"""

HANOI_WARDS: tuple[str, ...] = (
'''

FOOTER = ")\n"


def read_js_wards(js_text: str) -> list[str]:
    return WARD_LINE.findall(js_text)


def render(wards: list[str]) -> str:
    body = "".join(f'    "{ward}",\n' for ward in wards)
    return HEADER + body + FOOTER


def main() -> int:
    wards = read_js_wards(JS_FILE.read_text(encoding="utf-8"))
    if not wards:
        print("Không đọc được phường nào từ file JS.", file=sys.stderr)
        return 1
    if len(set(wards)) != len(wards):
        print("Danh mục JS có tên trùng lặp.", file=sys.stderr)
        return 1

    PY_FILE.write_text(render(wards), encoding="utf-8")
    # Giữ log thuần ASCII: console Windows mặc định cp1252 sẽ vỡ nếu in tiếng Việt.
    print(f"wrote {len(wards)} wards -> {PY_FILE.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
