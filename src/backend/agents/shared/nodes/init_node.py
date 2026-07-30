"""Node `init` — đóng dấu `channel` lên state ngay đầu mỗi lượt.

Mỗi graph tự gắn channel của mình thay vì trông vào frontend `setState`: chỉ cần
một lần quên là agent CRM nói giọng dành cho khách, mà lỗi đó không có test nào
bắt được vì graph vẫn chạy đúng.
"""

from typing import Any

from ..state import AgentState


def make_init_node(channel: str):
    async def init_node(state: AgentState) -> dict[str, Any]:  # noqa: ARG001
        return {"channel": channel}

    return init_node
