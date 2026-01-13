from dataclasses import dataclass
from pathlib import Path


@dataclass
class MyArticle:
    path: Path
    success: bool
    warning: str | None = None

    @property
    def has_warning(self) -> bool:
        return self.warning is not None
