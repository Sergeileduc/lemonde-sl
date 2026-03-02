from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from rich.panel import Panel
from rich.text import Text


@dataclass
class MyArticle:
    path: Path
    success: bool
    warning: str | None = None

    @property
    def has_warning(self) -> bool:
        return self.warning is not None

@dataclass
class Comment:
    id: str
    author: str
    content: str
    created_at: datetime
    likes: int
    parent_id: str | None
    replies: list["Comment"] = field(default_factory=list)

    def __rich__(self):
        title = f"- [bold red]{self.author}[/] ({self.created_at}) [{self.likes} likes]"
        text = Text(self.content, style="cyan")
        return Panel(text, title=title, title_align="left", border_style="green")
