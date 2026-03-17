import os
from pathlib import Path

from bs4 import BeautifulSoup

from lemonde_sl import LeMonde
from lemonde_sl.pdf_tools import build_pdf_html
from lemonde_sl.tools import fix_image_urls, limit_images_with_priority, simplify_picture_tags


def prepare_html(
    article_body: str,
    mobile: bool = False,
    dark: bool = False,
    max_img: int = 5,
    debug: bool = False,
) -> str:
    soup = BeautifulSoup(article_body, "html.parser")

    if debug:
        with open("soup1.html", "w", encoding="utf-8") as f:
            f.write(soup.prettify())

    target_size = 200 if mobile else 550
    simplify_picture_tags(soup, target_width=target_size)
    if debug:
        with open("soup2.html", "w", encoding="utf-8") as f:
            f.write(soup.prettify())

    fix_image_urls(soup, target_width=target_size)
    if debug:
        with open("soup3.html", "w", encoding="utf-8") as f:
            f.write(soup.prettify())

    limit_images_with_priority(soup, max_global=max_img)
    if debug:
        with open("soup4.html", "w", encoding="utf-8") as f:
            f.write(soup.prettify())

    return str(soup)


# CLEAN
exclude = ("venv", ".venv")
p = Path(".")
genpdf = (i for i in p.rglob("*.pdf") if not str(i.parent).startswith(exclude))
for art in genpdf:
    os.remove(art)

# MAIN

with open("raw-html.html", encoding="utf-8") as f:
    raw_html = f.read()

clean_html1 = prepare_html(raw_html, mobile=False, dark=False)
clean_html2 = prepare_html(raw_html, mobile=False, dark=True)
clean_html3 = prepare_html(raw_html, mobile=True, dark=False)
clean_html4 = prepare_html(raw_html, mobile=True, dark=True)


name1: str = "offline_pdf1.pdf"
name2: str = "offline_pdf2.pdf"
name3: str = "offline_pdf3.pdf"
name4: str = "offline_pdf4.pdf"

# Making HTML ready for pdf
full_html1, pdf_options1 = build_pdf_html(
    fragment=clean_html1,
    mobile=False,
    dark=False,
)
full_html2, pdf_options2 = build_pdf_html(
    fragment=clean_html2,
    mobile=False,
    dark=True,
)
full_html3, pdf_options3 = build_pdf_html(
    fragment=clean_html3,
    mobile=True,
    dark=False,
)
full_html4, pdf_options4 = build_pdf_html(
    fragment=clean_html4,
    mobile=True,
    dark=True,
)

# Making PDF
success, warning = LeMonde.to_pdf(full_html1, name1, pdf_options1)
success, warning = LeMonde.to_pdf(full_html2, name2, pdf_options2)
success, warning = LeMonde.to_pdf(full_html3, name3, pdf_options3)
success, warning = LeMonde.to_pdf(full_html4, name4, pdf_options4)
