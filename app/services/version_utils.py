"""版本工具：语义化版本解析与比较。

从 desktop/main.py 提取，避免测试导入 tkinter 依赖。
"""
from __future__ import annotations


def version_tuple(value: str) -> tuple[int, int, int]:
    """将语义化版本字符串解析为可比较的整数元组。"""
    parts = value.split(".")
    if len(parts) != 3 or any(not part.isdigit() for part in parts):
        raise ValueError("invalid semantic version")
    return tuple(int(part) for part in parts)
