import logging

from .client import Comment, LeMonde, LeMondeAsync, parse_comment
from .models import MyArticle

__all__ = ["LeMonde", "LeMondeAsync", "Comment", "parse_comment", "MyArticle"]

# Neutraliser les logs DEBUG très verbeux de fontTools (utilisé par WeasyPrint)
_font_logger = logging.getLogger("fontTools")
_font_logger.setLevel(logging.WARNING)
_font_logger.propagate = False
_font_logger.handlers.clear()
