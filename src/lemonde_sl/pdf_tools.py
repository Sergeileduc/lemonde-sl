# from dataclasses import dataclass
import os
from urllib.parse import urlparse

PRESETS = {
    "desk_light": {"mobile": False, "dark": False},
    "desk_dark": {"mobile": False, "dark": True},
    "mobile_light": {"mobile": True, "dark": False},
    "mobile_dark": {"mobile": True, "dark": True},
}


def _make_pdf_prefix(mobile: bool, dark: bool) -> str:
    """Generate prefix from settings.

    Example : desk_dark_
              or
              mobile_light_
    """
    mode = "mobile" if mobile else "desk"
    theme = "dark" if dark else "light"
    prefix = f"{mode}_{theme}_"
    # if prefix == "desk_light_":
    #     prefix = ""
    return prefix


def _get_slug(url: str) -> str:
    """Return a safe name derived from URL."""
    path = urlparse(url).path
    slug = path.rsplit("/", 1)[-1]
    base, _ = os.path.splitext(slug)
    return base


def make_pdf_name(url: str, mobile: bool, dark: bool) -> str:
    """Return name in form of prefix (from mobile and dark options) + slug from url"""
    prefix = _make_pdf_prefix(mobile, dark)
    base = _get_slug(url)
    return f"{prefix}{base}.pdf"


def build_pdf_html(
    fragment: str,
    mobile: bool = False,
    dark: bool = False,
) -> tuple[str, dict[str, str | list[tuple[str, str]] | None]]:
    """
    Build a full HTML document and PDFKit options for rendering an article.

    This function wraps a cleaned HTML fragment into a complete HTML document
    and generates the appropriate PDFKit configuration depending on the
    selected layout (mobile or desktop) and theme (light or dark).

    Args:
        fragment (str): Cleaned HTML content to insert into the <body>.
        mobile (bool): If True, use a compact mobile layout.
        dark (bool): If True, apply a dark theme suitable for night reading.

    Returns:
        tuple[str, dict]: A tuple containing:
            - The full HTML document as a string.
            - A dictionary of PDFKit options.
    """
    # Page format + spacing rules
    if mobile:
        page_size = "A6"
        # margin_mm = 7 if not dark else 0
        # padding_mm = 0 if not dark else 7
        margin_mm = 0
        padding_mm = 7
        font_size = 20  # px
        legend_size = 15  # px
    else:
        page_size = "A4"
        # margin_mm = 20 if not dark else 0
        # padding_mm = 0 if not dark else 20
        margin_mm = 0
        padding_mm = 30
        font_size = 18  # px
        legend_size = 16  # px

    # PDFKit options
    options = {
        "page-size": page_size,
        "margin-top": f"{margin_mm}mm",
        "margin-right": f"{margin_mm}mm",
        "margin-bottom": f"{margin_mm}mm",
        "margin-left": f"{margin_mm}mm",
        "encoding": "UTF-8",
        "no-outline": None,
        "custom-header": [("Accept-Encoding", "gzip")],
        "enable-local-file-access": "",
    }

    common_css = f"""
    <style>
    html {{
        background: transparent;
    }}
    body {{
        margin: 0;
        padding: {padding_mm}mm;
        font-family: sans-serif;
        font-size: {font_size}px;
        line-height: 1.6;
        box-sizing: border-box;
    }}
    img {{
        max-width: 100%;
        height: auto;
    }}
    .article__legend {{
        font-size: {legend_size}px;
        line-height: 1.3;
        margin-top: 4px;
        display: block;
        color: inherit;
    }}
    .article__legend .article__credit {{
        font-size: {legend_size - 2}px;
        color: inherit;
    }}
    </style>
    """

    if dark:
        theme_css = """
        <style>
        html { background: #121212; }
        body { background: transparent; color: #e0e0e0; }
        a { color: #90caf9; }
        </style>
        """
    else:
        theme_css = """
        <style>
        body { background: white; color: #000; }
        a { color: #0645ad; }
        </style>
        """

    css = common_css + theme_css

    # Final HTML
    html = f"""
        <html>
        <head>
            <meta charset="UTF-8">
            {css}
        </head>
        <body>
            {fragment}
        </body>
        </html>
        """
    return html.strip(), options
