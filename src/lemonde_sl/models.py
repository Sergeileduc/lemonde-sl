from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias


@dataclass
class MyArticle:
    path: Path
    success: bool
    warning: str | None = None

    @property
    def has_warning(self) -> bool:
        return self.warning is not None


# JSON
JSONType: TypeAlias = dict[str, "JSONType"] | list["JSONType"] | str | int | float | bool | None
JSONObject: TypeAlias = dict[str, JSONType]
JSONArray: TypeAlias = list[JSONType]
