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
    if prefix == "desk_light_":
        prefix = ""
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
) -> tuple[str, str]:
    """
    Build a full HTML document and weasyprint options for rendering an article.

    This function wraps a cleaned HTML fragment into a complete HTML document
    and generates the appropriate weasyprint configuration depending on the
    selected layout (mobile or desktop) and theme (light or dark).

    Args:
        fragment (str): Cleaned HTML content to insert into the <body>.
        mobile (bool): If True, use a compact mobile layout (A6).
        dark (bool): If True, apply a dark theme suitable for night reading.

    Returns:
        tuple[str, str]: A tuple containing:
            - The full HTML document as a string.
            - A str of Weazykit css.
    """

    # Page format + spacing rules
    # Page format + spacing rules
    if mobile:
        page_size = "100mm 2000mm"
        margin_mm = 5 if not dark else 0
        padding_mm = 0 if not dark else 5
        title_scale = 0.7
        legend_scale = 0.6

    else:
        page_size = "170mm 2500mm"
        margin_mm = 15 if not dark else 0
        padding_mm = 0 if not dark else 15
        title_scale = 1.0  # normal
        legend_scale = 1.0
    
    base_h1 = 1.4  # rem
    base_h2 = 1.3  # rem
    base_h3 = 1.2  # rem
    base_legend = 0.875  # rem

    h1_size = f"{base_h1 * title_scale}rem"
    h2_size = f"{base_h2 * title_scale}rem"
    h3_size = f"{base_h3 * title_scale}rem"
    legend_size = f"{base_legend * legend_scale}rem"

    # CSS @page (équivalent des options weasyprint)
    page_css = f"""
    @page {{
        size: {page_size};
        margin: {margin_mm}mm;
    }}
    """

    title_css = f"""
    h1 {{
        font-size: {h1_size};
        line-height: 1.2;
    }}

    h2 {{
        font-size: {h2_size};
        line-height: 1.3;
    }}

    h3 {{
        font-size: {h3_size};
        line-height: 1.3;
    }}
    .article__legend {{
        font-size: {legend_size};
        line-height: 1.3;
    }}

    """

    # Theme CSS
    if dark:
        theme_css = f"""
        html {{
            background: #121212;
        }}
        body {{
            background: transparent;
            color: #e0e0e0;
            margin: 0;
            padding: {padding_mm}mm;
            font-family: sans-serif;
            font-size: 12pt;
            line-height: 1.6;
            box-sizing: border-box;
        }}
        a {{
            color: #90caf9;
        }}
        img {{
            max-width: 100%;
            height: auto;
        }}
        """
    else:
        theme_css = f"""
        body {{
            font-family: sans-serif;
            font-size: 12pt;
            line-height: 1.6;
            padding: {padding_mm}mm;
        }}
        img {{
            max-width: 100%;
            height: auto;
        }}
        """

    # CSS final
    css_string = page_css + title_css + theme_css

    # HTML final
    html = f"""
    <html>
    <head>
        <meta charset="UTF-8">
    </head>
    <body>
        {fragment}
    </body>
    </html>
    """

    return html.strip(), css_string.strip()
