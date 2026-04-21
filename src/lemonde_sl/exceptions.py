class ArticleParseError(Exception):
    """Raised when the article body cannot be extracted."""


class PDFError(Exception):
    """Raised when PDF generation fails."""
