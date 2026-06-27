from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class SelectionItem:

    title: str

    subtitle: str = ""

    icon: str = "📄"

    payload: Any = None