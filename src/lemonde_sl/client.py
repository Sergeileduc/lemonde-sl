import asyncio
import logging
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from os import PathLike
from typing import Self
from urllib.parse import urljoin, urlparse

import httpx
import pdfkit
from dotenv import load_dotenv
from rich import print
from rich.panel import Panel
from rich.text import Text
from selectolax.lexbor import LexborHTMLParser, LexborNode

logger = logging.getLogger(__name__)


class LeMondeBase:
    load_dotenv()
    HOST = os.getenv("LM_SL_HOST") or ""
    SECURE_HOST = os.getenv("LM_SL_SECURE_HOST") or ""

    LOGIN_URL = urljoin(SECURE_HOST, "sfuser/connexion")
    LOGOUT_URL = urljoin(SECURE_HOST, "sfuser/deconnexion")

    login_headers = {"Referer": LOGIN_URL}

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
    }

    # Bloats in HTML
    CSS_BLOATS = [
        ".meta__social",
        "ul.breadcrumb",
        "ul.ds-breadcrumb",
        "section.article__reactions",
        "section.friend",
        "section.article__siblings",
        "aside.aside__iso.old__aside",
        "section.inread",
        "div.catcher__favorite",
        "a.Header__offer",
    ]

    # ---------------------------------------------------------
    # PARSE
    # ---------------------------------------------------------
    @classmethod
    def parse(cls, html: str) -> str | None:
        """Extract and clean the main article content from a LM HTML page.

        Locates the article body using CSS selectors, removes known UI elements
        (social widgets, breadcrumbs, sidebars, ads), and returns a cleaned HTML
        fragment suitable for PDF export.

        Args:
            html (str): Raw HTML content of a LM article page.

        Returns:
            str|None: Cleaned HTML fragment containing the article body, or ``None`` if the
            article structure cannot be found.
        """

        parser = LexborHTMLParser(html)
        article_body = parser.css_first("main > .article--content")
        if not article_body:
            logger.warning("Article body not found in HTML")
            return None

        # 1) Remove UI junk
        cls._remove_bloats(article_body)

        # 2) Fix lazy-loaded images BEFORE converting to HTML
        cls._fix_image_urls(article_body)

        # 3) Return cleaned HTML
        return article_body.html

    @staticmethod
    def _make_payload(raw_html: str, email: str, password: str) -> dict[str, str]:
        parser = LexborHTMLParser(raw_html)

        form = parser.css_first('form[method="post"]')
        if not form:
            raise RuntimeError("Login form not found")

        inputs = form.css("input")

        payload = {
            str(i.attributes["name"]): str(i.attributes.get("value", ""))
            for i in inputs
            if "name" in i.attributes
        }

        payload["email"] = email
        payload["password"] = password

        return payload

    @classmethod
    def _remove_bloats(cls, article: LexborNode) -> None:
        "Remove some bloats in the article soup."
        for c in cls.CSS_BLOATS:
            try:
                list_elements = article.css(c)
                for elem in list_elements:
                    elem.decompose()  # remove some bloats
                    logger.info("Element %s decomposed", c)
            except AttributeError:
                logger.info("FAILS to remove %s bloat in the article. Pass.", c)

    @staticmethod
    def make_pdf_name(url: str) -> str:
        """Return a safe PDF filename derived from a LM article URL."""
        path = urlparse(url).path
        slug = path.rsplit("/", 1)[-1]
        base, _ = os.path.splitext(slug)
        return f"{base}.pdf"

    @staticmethod
    def _build_pdf_html(
        fragment: str,
        mobile: bool = False,
        dark: bool = False,
    ) -> tuple[str, dict[str, str | list | None]]:
        """
        Build a full HTML document and PDFKit options for rendering an article.

        This function wraps a cleaned HTML fragment into a complete HTML document
        and generates the appropriate PDFKit configuration depending on the
        selected layout (mobile or desktop) and theme (light or dark).

        Args:
            fragment (str): Cleaned HTML content to insert into the <body>.
            mobile (bool): If True, use a compact mobile layout (A6).
            dark (bool): If True, apply a dark theme suitable for night reading.

        Returns:
            tuple[str, dict]: A tuple containing:
                - The full HTML document as a string.
                - A dictionary of PDFKit options.
        """

        # Page format + spacing rules
        if mobile:
            page_size = "A6"
            margin_mm = 7 if not dark else 0
            padding_mm = 0 if not dark else 7
        else:
            page_size = "A4"
            margin_mm = 20 if not dark else 0
            padding_mm = 0 if not dark else 20

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

        # Theme CSS
        if dark:
            css = f"""
            <style>
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
                    filter: brightness(0.8) contrast(1.2);
                    max-width: 100%;
                    height: auto;
                }}
            </style>
            """
        else:
            css = """
            <style>
                body {
                    font-family: sans-serif;
                    font-size: 12pt;
                    line-height: 1.6;
                }
            </style>
            """

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

    @staticmethod
    def to_pdf(
        html: str,
        output_path: str | PathLike[str],
        options: dict[str, str | list | None],
        remove_multimedia: bool = True,
    ) -> tuple[bool, str | None]:
        """
        Generate a PDF file from a fully constructed HTML document.

        This function assumes the HTML has already been wrapped in a complete
        <html> document with appropriate CSS and that PDFKit options have been
        prepared upstream (e.g., via build_pdf_html).

        Args:
            html (str): Full HTML document to render.
            output_path (str | PathLike[str]): Destination path for the PDF file.
            options (dict): PDFKit configuration options.
            remove_multimedia (bool): Whether to attempt a fallback cleanup.


        Raises:
            OSError: If wkhtmltopdf is missing or pdfkit fails.

        Returns:
            tuple[bool, str | None]:
                - success (bool)
                - optional warning message (str | None)
        """

        try:
            pdfkit.from_string(html, output_path=output_path, options=options)
            return True, None

        except OSError as e:
            logger.error("wkhtmltopdf failed on first attempt")
            logger.error(e)

            if not remove_multimedia:
                raise

            logger.warning("Retrying after removing multimedia embeds")

            # Remove multimedia blocks
            cleaned_html = LexborHTMLParser(html)
            for node in cleaned_html.css("div.multimedia-embed"):
                node.decompose()

            try:
                pdfkit.from_string(cleaned_html.html, output_path=output_path, options=options)
                return (
                    True,
                    "Multimedia content was removed because wkhtmltopdf could not render it.",
                )
            except Exception as e2:
                logger.error("Second attempt failed as well")
                logger.error(e2)
                raise

    @staticmethod
    def extract_page_id(url: str) -> str:
        m = re.search(r"_(\d+)_\d+\.html$", url)
        if not m:
            raise ValueError("Impossible d'extraire le pageId depuis l'URL")
        return m.group(1)

    @staticmethod
    def _fix_image_urls(article: LexborNode) -> None:
        """
        Normalize image URLs in an article by resolving lazy-loaded attributes.

        This function scans all <img> elements in the provided HTML tree and ensures
        that each image has a valid ``src`` attribute. Many news websites, including
        Le Monde, use lazy‑loading techniques where the actual image URL is stored
        in attributes such as ``data-srcset`` or ``data-src``. These attributes are
        not interpreted by PDF generators (e.g., wkhtmltopdf), which results in
        missing images in the final output.

        The function extracts the most appropriate image URL from ``data-srcset``—
        typically the "664w" or "1x" variant—and assigns it to ``src``. If
        ``data-srcset`` is not available, it falls back to ``data-src``.

        Args:
            tree (LexborNode): A parsed HTML document or subtree from selectolax.

        Returns:
            None: The function mutates the HTML tree in place.
        """
        for img in article.css("img"):
            # 1) data-srcset → choisir la meilleure image
            if img.attributes.get("data-srcset"):
                srcset = img.attributes["data-srcset"].split(",")
                # On prend la première image "large" ou "1x"
                for candidate in srcset:
                    if "664w" in candidate or "1x" in candidate:
                        url = candidate.strip().split(" ")[0]
                        img.attributes["src"] = url
                        break

            # 2) fallback : data-src
            elif img.attributes.get("data-src"):
                img.attributes["src"] = img.attributes["data-src"]


class LeMonde(LeMondeBase):
    def __init__(self):
        # Le client vit aussi longtemps que l'objet
        self.client = httpx.Client(
            headers=self.headers,
            follow_redirects=True,
            timeout=10.0,
        )

    def login(self, email: str, password: str) -> bool:
        """Authenticate to LM using email and password (synchronous).

        Loads the login page, extracts the form payload, and submits the credentials.
        After login, premium cookies should be present in the session.

        Args:
            email (str): LM account email.
            password (str): LM account password.

        Raises:
            RuntimeError: If the login form cannot be found in the HTML.
            httpx.HTTPStatusError: If the GET or POST request fails.
        """
        resp = self.client.get(self.LOGIN_URL)
        resp.raise_for_status()
        raw_html = resp.text

        payload = self._make_payload(raw_html=raw_html, email=email, password=password)

        time.sleep(0.5)

        headers = {**self.headers, "Referer": self.LOGIN_URL}
        resp2 = self.client.post(self.LOGIN_URL, data=payload, headers=headers)
        resp2.raise_for_status()
        time.sleep(0.5)
        if "lmd_a_s" in self.client.cookies:
            print("✅ Login LM OK — cookie premium présent")
            return True
        else:
            print("❌ Login LM FAIL — cookie premium absent")
            return False

    def logout(self) -> None:
        """Log out from the LM session (synchronous).

        Sends a GET request to the logout endpoint. This invalidates premium cookies
        and ends the authenticated session.

        Raises:
            httpx.HTTPStatusError: If the logout request fails.
        """
        r = self.client.get(self.LOGOUT_URL)
        print("✅ Logout:", r.status_code)

    def fetch(self, url: str) -> str:
        """Fetch an article (synchronous).

        Sends an authenticated GET request using ``httpx.Client`` and returns the
        decoded HTML body. Raises an exception if the HTTP response indicates an
        error.

        Args:
            url (str): Full URL of the LM article to retrieve.

        Returns:
            str: The raw HTML content of the page.

        Raises:
            httpx.HTTPStatusError: If the server returns a 4xx or 5xx status code.
        """
        resp = self.client.get(url)
        resp.raise_for_status()
        logger.info("webpage correctly fetched : %s", url)
        return resp.text

    def fetch_and_parse(self, url: str) -> str | None:
        """Fetch and parse an article (sync).

        Sends an authenticated GET request using ``httpx.Client``
        and extract and clean the main article content from a LM HTML page.

        Locates the article body using CSS selectors, removes known UI elements
        (social widgets, breadcrumbs, sidebars, ads), and returns a cleaned HTML
        fragment suitable for PDF export.. Raises an exception if the HTTP response indicates
        an error.

        Args:
            url (str): Full URL of the article to retrieve.

        Returns:
            str|None: Cleaned HTML fragment containing the article body, or ``None`` if the
            article structure cannot be found.

        Raises:
            httpx.HTTPStatusError: If the server returns a 4xx or 5xx status code.
        """
        html = self.fetch(url)
        return self.parse(html)

    def fetch_pdf(
        self,
        url: str,
        email: str | None = None,
        password: str | None = None,
        mobile: bool = False,
        dark: bool = False,
    ) -> tuple[bool, str | None, str]:
        """
        Télécharge un article, le nettoie et génère un PDF.

        Cette méthode est une façade ergonomique qui enchaîne automatiquement :
        1. Le login (si `email` et `password` sont fournis)
        2. Le fetch de la page HTML
        3. Le parsing / nettoyage
        4. La génération du nom de fichier PDF
        5. L'export du PDF sur disque

        Args:
            url (str): URL de l'article à télécharger.
            email (str | None): Email utilisé pour le login. Si None, aucun login n'est effectué.
            password (str | None): Mot de passe associé. Si None, aucun login n'est effectué.

        Returns:
            bool: success de la création du PDF
            str | None : message d'erreur pendant la création du PDF
            str: Chemin du fichier PDF généré.

        Raises:
            RuntimeError: Si l'article ne peut pas être récupéré ou nettoyé.
            LoginError: Si le login échoue (si implémenté dans ta classe).
            ValueError: Si l'URL est invalide.
        """

        if email and password:
            self.login(email, password)

        clean_html = self.fetch_and_parse(url)
        if not clean_html:
            raise RuntimeError("Impossible de parser l'article")
        full_html, pdf_options = self._build_pdf_html(
            fragment=clean_html,
            mobile=mobile,
            dark=dark,
        )
        output_path = self.make_pdf_name(url)
        success, warning = self.to_pdf(full_html, output_path, pdf_options)

        return success, warning, output_path

    def close(self):
        self.client.close()

    def __del__(self) -> None:
        try:
            self.client.close()
        except Exception:
            pass

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            self.logout()
            logger.info("Logout OK in __exit__")
        except Exception:
            logger.error("Error in __exit__ logout")

        try:
            self.close()
            logger.info("client.close() OK in __exit__")
        except Exception:
            logger.error("Error in __exit__ client.close")

    def __rich__(self) -> Panel:
        lines = [
            "Objet LeMonde (sync)",
            f"client = {type(self.client).__name__}",
            "mode = sync",
        ]
        text = Text("\n".join(lines), style="cyan")
        return Panel(text, title="LeMonde", title_align="left", border_style="blue")

    def fetch_comments(self, page_id: str, page: int = 1, limit: int = 20) -> dict:
        url = (
            f"{self.HOST}/ajax/feedbacks/page"
            f"?pageId={page_id}&page={page}&limit={limit}&order=likes"
        )
        resp = self.client.get(url)
        resp.raise_for_status()
        return resp.json()


class LeMondeAsync(LeMondeBase):
    def __init__(self):
        self.client = httpx.AsyncClient(
            headers=self.headers,
            follow_redirects=True,
            timeout=10.0,
        )

    async def login(self, email: str, password: str) -> None:
        """Authenticate to LM using email and password (asynchronous).

        Loads the login page, extracts the form payload, and submits the credentials.
        After login, premium cookies should be present in the session.

        Args:
            email (str): LM account email.
            password (str): LM account password.

        Raises:
            RuntimeError: If the login form cannot be found in the HTML.
            httpx.HTTPStatusError: If the GET or POST request fails.
        """

        resp = await self.client.get(self.LOGIN_URL)
        resp.raise_for_status()
        raw_html = resp.text

        payload = self._make_payload(raw_html=raw_html, email=email, password=password)

        await asyncio.sleep(0.5)

        headers = {**self.headers, "Referer": self.LOGIN_URL}
        resp2 = await self.client.post(self.LOGIN_URL, data=payload, headers=headers)
        resp2.raise_for_status()

        if "lmd_a_s" in self.client.cookies:
            print("✅ Login LM OK — cookie premium présent")
        else:
            print("❌ Login LM FAIL — cookie premium absent")
        await asyncio.sleep(0.5)

    async def fetch(self, url: str) -> str:
        """Fetch a LM article (asynchronous).

        Sends an authenticated GET request using ``httpx.AsyncClient`` and returns
        the decoded HTML body. Raises an exception if the HTTP response indicates
        an error.

        Args:
            url (str): Full URL of the LM article to retrieve.

        Returns:
            str: The raw HTML content of the page.

        Raises:
            httpx.HTTPStatusError: If the server returns a 4xx or 5xx status code.
        """
        resp = await self.client.get(url)
        resp.raise_for_status()
        return resp.text

    async def fetch_and_parse(self, url: str) -> str | None:
        """Fetch and parse a LM article (asynchronous).

        Sends an authenticated GET request using ``httpx.AsyncClient``
        and extract and clean the main article content from a LM HTML page.

        Locates the article body using CSS selectors, removes known UI elements
        (social widgets, breadcrumbs, sidebars, ads), and returns a cleaned HTML
        fragment suitable for PDF export.. Raises an exception if the HTTP response indicates
        an error.

        Args:
            url (str): Full URL of the LM article to retrieve.

        Returns:
            str|None: Cleaned HTML fragment containing the article body, or ``None`` if the
            article structure cannot be found.

        Raises:
            httpx.HTTPStatusError: If the server returns a 4xx or 5xx status code.
        """
        html = await self.fetch(url)
        return self.parse(html)

    async def fetch_pdf(
        self,
        url: str,
        email: str | None = None,
        password: str | None = None,
        mobile: bool = False,
        dark: bool = False,
    ) -> tuple[bool, str | None, str]:
        """
        Télécharge un article LM, le nettoie et génère un PDF.

        Cette méthode est une façade ergonomique qui enchaîne automatiquement :
        1. Le login (si `email` et `password` sont fournis)
        2. Le fetch de la page HTML
        3. Le parsing / nettoyage
        4. La génération du nom de fichier PDF
        5. L'export du PDF sur disque

        Args:
            url (str): URL de l'article LM à télécharger.
            email (str | None): Email utilisé pour le login. Si None, aucun login n'est effectué.
            password (str | None): Mot de passe associé. Si None, aucun login n'est effectué.

        Returns:
            bool: success de la création du PDF
            str | None : message d'erreur pendant la création du PDF
            str: Chemin du fichier PDF généré.

        Raises:
            RuntimeError: Si l'article ne peut pas être récupéré ou nettoyé.
            LoginError: Si le login échoue (si implémenté dans ta classe).
            ValueError: Si l'URL est invalide.
        """
        # 1) login si credentials fournis
        if email and password:
            await self.login(email, password)

        # 2) fetch + parse
        clean_html = await self.fetch_and_parse(url)
        if not clean_html:
            raise RuntimeError("Impossible de parser l'article")

        full_html, pdf_options = self._build_pdf_html(
            fragment=clean_html,
            mobile=mobile,
            dark=dark,
        )

        # 3) compute filename
        output_path = self.make_pdf_name(url)

        # 4) generate PDF
        success, warning = self.to_pdf(full_html, output_path=output_path, options=pdf_options)

        return output_path

    async def logout(self) -> None:
        """Log out from the LM session (asynchronous).

        Sends a GET request to the logout endpoint. This invalidates premium cookies
        and ends the authenticated session.

        Raises:
            httpx.HTTPStatusError: If the logout request fails.
        """
        r = await self.client.get(self.LOGOUT_URL)
        print("✅ Logout:", r.status_code)

    async def close(self) -> None:
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        try:
            await self.logout()
            logger.info("Logout OK in __aexit__")
        except Exception:
            logger.error("Error in __aexit__ logout")

        try:
            await self.client.aclose()
            logger.info("client.close() OK in __exit__")
        except Exception:
            logger.error("Error in __exit__ client.close")

    def __rich__(self) -> Panel:
        lines = [
            "Objet LeMondeAsync (async)",
            f"client = {type(self.client).__name__}",
            "mode = async",
        ]
        text = Text("\n".join(lines), style="cyan")
        return Panel(text, title="LeMondeAsync", title_align="left", border_style="blue")

    async def fetch_comments(self, page_id: str, page: int = 1, limit: int = 20) -> dict:
        url = (
            f"{self.HOST}/ajax/feedbacks/page"
            f"?pageId={page_id}&page={page}&limit={limit}&order=likes"
        )
        resp = await self.client.get(url)
        resp.raise_for_status()
        return resp.json()


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


def parse_comment(data: dict) -> Comment:
    replies = [parse_comment(r) for r in data.get("replies", [])]

    return Comment(
        id=data["commentId"],
        author=data["userName"],
        content=data["content"],
        created_at=datetime.fromisoformat(data["createdAt"].replace("Z", "+00:00")),
        likes=data["likes"],
        parent_id=data["parentId"],
        replies=replies,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARN)
    # logger.warning("Start")

    # Login credentials
    load_dotenv()
    email = os.getenv("LM_SL_EMAIL") or ""
    password = os.getenv("LM_SL_PASSWD") or ""
    URL1 = os.getenv("LM_SL_TEST_URL1") or ""
    URL2 = os.getenv("LM_SL_TEST_URL2") or ""

    # def main() -> None:
    #     # Version Sync
    #     print("Version SYNC")
    #     lm = LeMonde()
    #     lm.login(email, password)
    #     clean = lm.fetch_and_parse(URL1)

    #     if clean:
    #         full_name = URL.rsplit('/', 1)[-1]
    #         output_file: str = f"{os.path.splitext(full_name)[0]}.pdf"
    #         print(f"Generate PDF file: {output_file}")
    #         lm.to_pdf(clean, output_path=output_file)
    #     lm.logout()
    #     lm.close()

    # # Version Async
    # async def amain() -> None:
    #     print("Version ASYNC")
    #     lm = LeMondeAsync()
    #     await lm.login(email, password)
    #     clean = await lm.fetch_and_parse(URL2)

    #     if clean:
    #         full_name = URL.rsplit('/', 1)[-1]
    #         output_file: str = f"{os.path.splitext(full_name)[0]}.pdf"
    #         print(f"Generate PDF file: {output_file}")
    #         lm.to_pdf(clean, output_path=output_file)
    #     await lm.logout()
    #     await lm.close()

    # main()
    # time.sleep(0.5)
    # asyncio.run(amain())

    def main_context():
        print("Version SYNC")
        with LeMonde() as lm:
            print(lm)
            # LEGACY : step by step
            # lm.login(email, password)
            # clean = lm.fetch_and_parse(URL1)
            # if clean:
            #     output_file = lm.make_pdf_name(URL1)
            #     print(f"Generate PDF file: {output_file}")
            #     lm.to_pdf(clean, output_path=output_file)
            # NEW CODE : one line !
            success, warning, path = lm.fetch_pdf(
                url=URL1, email=email, password=password, mobile=False, dark=True
            )
            print(success, warning, path)
            # id = lm.extract_page_id(URL1)
            # print(f"Extracted page ID: {id}")
            # json_data = lm.fetch_comments(page_id=id, page=1, limit=5)
            # comments = [parse_comment(c) for c in json_data["comments"]]
            # for c in comments:
            #     print(c)

    async def amain_context():
        print("Version ASYNC")
        async with LeMondeAsync() as lm:
            print(lm)
            # LEGACY : step by step
            # await lm.login(email, password)
            # clean = await lm.fetch_and_parse(URL)
            # if clean:
            #     output_file = lm.make_pdf_name(URL)
            #     print(f"Generate PDF file: {output_file}")
            #     lm.to_pdf(clean, output_path=output_file)
            # NEW CODE : one line !
            await lm.fetch_pdf(url=URL2, email=email, password=password, mobile=True, dark=True)
            # id = lm.extract_page_id(URL2)
            # print(f"Extracted page ID: {id}")
            # json_data = await lm.fetch_comments(page_id=id, page=1, limit=5)
            # comments = [parse_comment(c) for c in json_data["comments"]]
            # for c in comments:
            #     print(c)

    main_context()
    time.sleep(0.5)
    asyncio.run(amain_context())
