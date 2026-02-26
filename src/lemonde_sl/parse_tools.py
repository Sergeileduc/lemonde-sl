import logging
import re

from selectolax.parser import HTMLParser, Node

logger = logging.getLogger(__name__)


def extract_page_id(url: str) -> str:
    m = re.search(r"_(\d+)_\d+\.html$", url)
    if not m:
        raise ValueError("Impossible d'extraire le pageId depuis l'URL")
    return m.group(1)


def _remove_bloats(article: Node, bloats: list = []) -> None:
    "Remove some bloats in the article soup."
    for c in bloats:
        try:
            list_elements = article.css(c)
            for elem in list_elements:
                elem.decompose()  # remove some bloats
                logger.info("Element %s decomposed", c)
        except AttributeError:
            logger.info("FAILS to remove %s bloat in the article. Pass.", c)


def parse_style(style: str) -> tuple[bool, bool]:
    """Convert a string like "normal_light" or "mobile_dark" in booleans.

    Args:
        style (str): description of the style (ex: mobile_dark)

    Returns:
        tuple[bool, bool]: mobile, dark
    """
    parts = style.split("_")
    mobile = "mobile" in parts
    dark = "dark" in parts
    return mobile, dark
