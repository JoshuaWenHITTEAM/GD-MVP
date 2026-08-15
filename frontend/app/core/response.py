from __future__ import annotations

from typing import Any, Dict


def success(data: Any) -> Dict[str, Any]:
    return {
        'code': 0,
        'message': 'success',
        'data': data,
    }
