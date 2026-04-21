import asyncio
import logging
import os
import time
from abc import ABC, abstractmethod
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Self
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from rich import print
from rich.panel import Panel
from rich.text import Text
from selectolax.parser import HTMLParser, Node

from .exceptions import ArticleParseError, PDFError
from .models import Comment, JSONObject, MyArticle
from .parse_tools import parse_style
from .pdf_tools import build_pdf_html, make_pdf_name, render_pdf_sync
from .tools import fix_image_urls, limit_images_with_priority, simplify_picture_tags
from .types import PathType

logger = logging.getLogger(__name__)


PDF_EXECUTOR = ProcessPoolExecutor(
    max_workers=1
)  # Un seul worker pour éviter les corruptions internes


class LeMondeBase(ABC):
    load_dotenv()
    HOST = os.getenv("LM_SL_HOST") or ""
    SECURE_HOST = os.getenv("LM_SL_SECURE_HOST") or ""

    LOGIN_URL = urljoin(SECURE_HOST, "sfuser/connexion")
    LOGOUT_URL = urljoin(SECURE_HOST, "sfuser/deconnexion")

    login_headers = {"Referer": LOGIN_URL}

    headers_login = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
    }

    headers_article = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
        ),
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Referer": "https://www.google.com/",
        # Cookie Didomi minimal (consentement générique)
        # "Cookie": "didomi_token=eyJ1c2VyX2lkIjoiZHVtbXkifQ==",
    }

    # Bloats in HTML
    CSS_BLOATS = [
        ".meta__social",
        ".services-carousel",
        "a.Header__offer",
        "aside.aside__iso.old__aside",
        "div.catcher__favorite",
        "div.multimedia-embed",
        "noscript",
        "section.article__reactions",
        "section.article__siblings",
        "section.js-portfolio-controls",
        "section.js-portfolio-fs",
        "section.js-portfolio-pagination",
        "section.portfolio__fs-open-container",
        "section.friend",
        "section.inread",
        "ul.breadcrumb",
        "ul.ds-breadcrumb",
    ]

    # ---------------------------------------------------------
    # PARSE
    # ---------------------------------------------------------
    @classmethod
    def parse(cls, html: str) -> str:
        """Extract and clean the main article content from a LM HTML page.

        Locates the article body using CSS selectors, removes known UI elements
        (social widgets, breadcrumbs, sidebars, ads), and returns a cleaned HTML
        fragment suitable for PDF export.

        Args:
            html (str): Raw HTML content of a LM article page.

        Returns:
            str|None: Cleaned HTML fragment containing the article body, or ``None`` if the
            article structure cannot be found.

        Raises:
            ArticleParseError
        """
        # 1) Selectolax : extraction + nettoyage structurel
        parser = HTMLParser(html)

        article_body = parser.css_first("main > .article--content")
        if not article_body:
            raise ArticleParseError("Article body not found in HTML")

        # Remove UI junk
        cls._remove_bloats(article_body)

        return article_body.html  # type: ignore[no-any-return,unused-ignore]

    @staticmethod
    def _make_payload(raw_html: str, email: str, password: str) -> dict[str, str]:
        parser = HTMLParser(raw_html)

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
    def _remove_bloats(cls, article: Node) -> None:
        "Remove some bloats in the article soup."
        for c in cls.CSS_BLOATS:
            try:
                list_elements = article.css(c)
                for elem in list_elements:
                    elem.decompose()  # remove some bloats
                    logger.info("Element %s decomposed", c)
            except AttributeError:
                logger.info("FAILS to remove %s bloat in the article. Pass.", c)

    @abstractmethod
    def to_pdf(self, *args, **kwargs):
        """Convert HTML to PDF (sync or async depending on subclass)."""
        raise NotImplementedError

    @abstractmethod
    def fetch_pdf(self, *args, **kwargs):
        """Fetch PDF (sync or async depending on subclass)."""
        raise NotImplementedError


class LeMonde(LeMondeBase):
    def __init__(self):
        # Le client vit aussi longtemps que l'objet
        self.client = httpx.Client(
            headers=self.headers_login,
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
        resp = self.client.get(self.LOGIN_URL, headers=self.headers_login)
        resp.raise_for_status()
        raw_html = resp.text

        payload = self._make_payload(raw_html=raw_html, email=email, password=password)

        time.sleep(0.5)

        headers = {**self.headers_login, "Referer": self.LOGIN_URL}
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
        resp = self.client.get(url, headers=self.headers_article)
        resp.raise_for_status()
        logger.info("webpage correctly fetched : %s", url)
        return resp.text  # type: ignore[no-any-return,unused-ignore]

    def fetch_and_parse(self, url: str) -> str:
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
            str: Cleaned HTML fragment containing the article body

        Raises:
            httpx.HTTPStatusError: If the server returns a 4xx or 5xx status code.
            ArticleParseError if the article body cannot be extracted
        """
        html = self.fetch(url=url)
        return self.parse(html)

    def _fetch_article_body(
        self,
        url: str,
        email: str | None,
        password: str | None,
    ) -> str:
        """Login éventuel + fetch + parse, avec log + re-raise."""
        if email and password:
            self.login(email, password)

        try:
            return self.fetch_and_parse(url=url)
        except ArticleParseError as e:
            logger.warning("Impossible de parser l'article %s: %s", url, e)
            raise

    def fetch_pdf(
        self,
        url: str,
        email: str | None = None,
        password: str | None = None,
        mobile: bool = False,
        dark: bool = False,
        max_img: int = 50,
    ) -> MyArticle:
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
            mobile (bool) : mode mobile. Default to False
            dark (bool) : dark mode. Default to False
            max_img (int) : Max imgs to load (critical for memory).

        Returns:
            MyArticle

        Raises:
            LoginError: Si le login échoue (si implémenté dans ta classe).
            ValueError: Si l'URL est invalide.
            ArticleParseError: If the article body cannot be extracted.
        """

        article_body = self._fetch_article_body(url, email, password)

        output_path = make_pdf_name(url, mobile=mobile, dark=dark)
        return self.render_variant_pdf(
            article_body,
            name=output_path,
            mobile=mobile,
            dark=dark,
            max_img=max_img,
        )

    def fetch_multiple_pdf(
        self,
        url: str,
        matrix: list[str],
        email: str | None = None,
        password: str | None = None,
        max_img: int = 50,
    ) -> list[MyArticle]:
        """
        Télécharge un article, le nettoie et génère 1 ou plusieurs PDF selon une matrice.
        Exemple de matrice : ["normal_light, "mobile_dark", "mobile_light"]

        Cette méthode est une façade ergonomique qui enchaîne automatiquement :
        1. Le login (si `email` et `password` sont fournis)
        2. Le fetch de la page HTML
        3. Le parsing / nettoyage
        4. La génération du nom de plusieurs fichiers PDFs
        5. L'export du/des PDF(s) sur disque

        Args:
            url (str): URL de l'article à télécharger.
            email (str | None): Email utilisé pour le login. Si None, aucun login n'est effectué.
            password (str | None): Mot de passe associé. Si None, aucun login n'est effectué.
            matrix (list): liste des fichiers attendus (["normaldark", "mobilelight", etc])
            max_img (int): Max imgs to load (critical for memory).

        Returns:
            list[MyArticle]

        Raises:
            LoginError: Si le login échoue (si implémenté dans ta classe).
            ValueError: Si l'URL est invalide.
            ArticleParseError: If the article body cannot be extracted.
        """

        article_body = self._fetch_article_body(url, email, password)

        my_articles = []
        for style in matrix:
            mobile, dark = parse_style(style)
            name = make_pdf_name(url, mobile=mobile, dark=dark)
            article = self.render_variant_pdf(
                article_body,
                name=name,
                mobile=mobile,
                dark=dark,
                max_img=max_img,
            )
            my_articles.append(article)

        return my_articles

    def fetch_all_pdf(
        self,
        url: str,
        email: str | None = None,
        password: str | None = None,
        max_img: int = 50,
    ) -> list[MyArticle]:
        matrix = ["normal_light", "normal_dark", "mobile_light", "mobile_dark"]
        return self.fetch_multiple_pdf(
            url=url, email=email, password=password, matrix=matrix, max_img=max_img
        )

    def render_variant_pdf(
        self,
        article_body: str,
        name: str,
        mobile: bool = False,
        dark: bool = False,
        max_img: int = 50,
    ) -> MyArticle:
        """Makes a pdf from article_body.
        Should be called after login and after fetch_and_parse.

        Args:
            article_body (str): html to render
            name (str): name of .pdf file to generate
            mobile (bool, optional): mobile mode. Defaults to False.
            dark (bool, optional): dark theme mode. Defaults to False.
            max_img (int, optional): max images to load. Defaults to 50.

        Returns:
            MyArticle: _description_
        """
        # Clean images with BeautifulSoup before giving to PDF generation
        soup = BeautifulSoup(article_body, "html.parser")
        target_size = 200 if mobile else 550
        simplify_picture_tags(soup, target_width=target_size)
        fix_image_urls(soup, target_width=target_size)
        limit_images_with_priority(soup, max_global=max_img)
        clean_html = str(soup)

        # Making HTML ready for pdf
        full_html, pdf_options = build_pdf_html(
            fragment=clean_html,
            mobile=mobile,
            dark=dark,
        )

        # Making PDF
        success, warning = self.to_pdf(full_html, name, pdf_options)

        # return success, warning, output_path
        return MyArticle(
            path=Path(name),
            success=success,
            warning=warning,
        )

    @staticmethod
    def to_pdf(
        html: str,
        output_path: PathType,
        css: str,
        remove_multimedia: bool = True,
    ) -> tuple[bool, str | None]:
        """
        Generate a PDF file from a fully constructed HTML document.

        This function assumes the HTML has already been wrapped in a complete
        <html> document with appropriate CSS and that weasypring options have been
        prepared upstream (e.g., via build_pdf_html).

        Args:
            html (str): Full HTML document to render.
            output_path (str | PathLike[str]): Destination path for the PDF file.
            css (str): WeasyPrint configuration options. CSS string.
            remove_multimedia (bool): Whether to attempt a fallback cleanup.


        Raises:
            PDFError

        Returns:
            tuple[bool, str | None]:
                - success (bool)
                - optional warning message (str | None)
        """

        logger.info("Starting weasyprint")

        try:
            render_pdf_sync(html, css, output_path)
            logger.info("Weasyprint done into %s", output_path)
            return True, None

        except OSError as e:
            logger.error("WeasyPrint failed on first attempt: %s", e)

            if not remove_multimedia:
                raise PDFError(f"WeasyPrint failed: {e}") from e

            logger.warning("Retrying after removing multimedia embeds")

            # Remove multimedia blocks
            cleaned_html = HTMLParser(html)
            for node in cleaned_html.css("div.multimedia-embed"):
                node.decompose()

            cleaned = cleaned_html.html
            assert cleaned is not None  # invariant: cleaned_html.html is always a string

            try:
                # ⚠️ we use cleaned_html.html
                render_pdf_sync(cleaned, css, output_path)
                logger.info("Weasyprint succeeded after cleanup")
                return True, None

            except Exception as e2:
                logger.error("Second attempt failed as well: %s", e2)
                raise PDFError(f"WeasyPrint failed after cleanup: {e2}") from e2

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

    def fetch_comments(self, page_id: str, page: int = 1, limit: int = 20) -> JSONObject:
        url = (
            f"{self.HOST}/ajax/feedbacks/page"
            f"?pageId={page_id}&page={page}&limit={limit}&order=likes"
        )
        resp = self.client.get(url)
        resp.raise_for_status()
        return resp.json()  # type: ignore


class LeMondeAsync(LeMondeBase):
    def __init__(self):
        self.client = httpx.AsyncClient(
            headers=self.headers_login,
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

        headers = {**self.headers_login, "Referer": self.LOGIN_URL}
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
        resp = await self.client.get(url, headers=self.headers_article)
        resp.raise_for_status()
        return resp.text  # type: ignore[no-any-return,unused-ignore]

    async def fetch_and_parse(self, url: str) -> str:
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
            str: Cleaned HTML fragment containing the article body

        Raises:
            httpx.HTTPStatusError: If the server returns a 4xx or 5xx status code.
            ArticleParseError: If the article body cannot be extracted.
        """
        html = await self.fetch(url)
        return self.parse(html)

    async def _fetch_article_body(
        self,
        url: str,
        email: str | None,
        password: str | None,
    ) -> str:
        """Login éventuel + fetch + parse, avec log + re-raise (async)."""

        if email and password:
            await self.login(email, password)

        try:
            return await self.fetch_and_parse(url)
        except ArticleParseError as e:
            logger.warning("Impossible de parser l'article %s: %s", url, e)
            raise

    async def fetch_pdf(
        self,
        url: str,
        email: str | None = None,
        password: str | None = None,
        mobile: bool = False,
        dark: bool = False,
        max_img: int = 50,
    ) -> MyArticle:
        """
        Télécharge un article LM, le nettoie et génère un PDF.

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
            mobile (bool) : mode mobile. Default to False
            dark (bool) : dark mode. Default to False
            max_img (int) : Max imgs to load (critical for memory).

        Returns:
            MyArticle

        Raises:
            LoginError: Si le login échoue (si implémenté dans ta classe).
            ValueError: Si l'URL est invalide.
            ArticleParseError: If the article body cannot be extracted.
        """
        article_body = await self._fetch_article_body(url, email, password)

        output_path = make_pdf_name(url, mobile=mobile, dark=dark)

        return await self.render_variant_pdf(
            article_body,
            name=output_path,
            mobile=mobile,
            dark=dark,
            max_img=max_img,
        )

    async def fetch_multiple_pdf(
        self,
        url: str,
        matrix: list[str],
        email: str | None = None,
        password: str | None = None,
        max_img: int = 50,
    ) -> list[MyArticle]:
        """
        Télécharge un article, le nettoie et génère 1 ou plusieurs PDF selon une matrice.
        Exemple de matrice : ["normal_light, "mobile_dark", "mobile_light"]

        Cette méthode est une façade ergonomique qui enchaîne automatiquement :
        1. Le login (si `email` et `password` sont fournis)
        2. Le fetch de la page HTML
        3. Le parsing / nettoyage
        4. La génération du nom de plusieurs fichiers PDFs
        5. L'export du/des PDF(s) sur disque

        Args:
            url (str): URL de l'article à télécharger.
            email (str | None): Email utilisé pour le login. Si None, aucun login n'est effectué.
            password (str | None): Mot de passe associé. Si None, aucun login n'est effectué.
            matrix (list): liste des fichiers attendus (["normaldark", "mobilelight", etc])
            max_img (int): Max imgs to load (critical for memory).

        Returns:
            list[MyArticle]

        Raises:
            LoginError: Si le login échoue (si implémenté dans ta classe).
            ValueError: Si l'URL est invalide.
            ArticleParseError: If the article body cannot be extracted.
        """

        article_body = await self._fetch_article_body(url, email, password)

        my_articles: list[MyArticle] = []

        for style in matrix:
            mobile, dark = parse_style(style)
            name = make_pdf_name(url, mobile=mobile, dark=dark)

            article = await self.render_variant_pdf(
                article_body,
                name=name,
                mobile=mobile,
                dark=dark,
                max_img=max_img,
            )
            my_articles.append(article)

        return my_articles

    async def fetch_all_pdf(
        self,
        url: str,
        email: str | None = None,
        password: str | None = None,
        max_img: int = 50,
    ) -> list[MyArticle]:
        matrix = ["normal_light", "normal_dark", "mobile_light", "mobile_dark"]
        return await self.fetch_multiple_pdf(
            url=url, email=email, password=password, matrix=matrix, max_img=max_img
        )

    async def render_variant_pdf(
        self,
        article_body: str,
        name: str,
        mobile: bool = False,
        dark: bool = False,
        max_img: int = 50,
    ) -> MyArticle:
        """ "Makes a pdf from article_body.
        Should be called after login and after fetch_and_parse.
        """
        # Clean images with BeautifulSoup before giving to PDF generation
        soup = BeautifulSoup(article_body, "html.parser")
        target_size = 200 if mobile else 550
        simplify_picture_tags(soup, target_width=target_size)
        fix_image_urls(soup, target_width=target_size)
        limit_images_with_priority(soup, max_global=max_img)
        clean_html = str(soup)

        # Making HTML ready for pdf
        full_html, pdf_options = build_pdf_html(
            fragment=clean_html,
            mobile=mobile,
            dark=dark,
        )

        # Making PDF
        success, warning = await self.to_pdf(full_html, name, pdf_options)

        # return success, warning, output_path
        return MyArticle(
            path=Path(name),
            success=success,
            warning=warning,
        )

    async def logout(self) -> None:
        """Log out from the LM session (asynchronous).

        Sends a GET request to the logout endpoint. This invalidates premium cookies
        and ends the authenticated session.

        Raises:
            httpx.HTTPStatusError: If the logout request fails.
        """
        r = await self.client.get(self.LOGOUT_URL)
        print("✅ Logout:", r.status_code)

    async def to_pdf(
        self,
        html: str,
        output_path: PathType,
        css: str,
        remove_multimedia: bool = True,
    ) -> tuple[bool, str | None]:
        """
        Generate a PDF file from a fully constructed HTML document.

        This function assumes the HTML has already been wrapped in a complete
        <html> document with appropriate CSS and that weasyprint options have been
        prepared upstream (e.g., via build_pdf_html).

        Args:
            html (str): Full HTML document to render.
            output_path (str | PathLike[str]): Destination path for the PDF file.
            css (str): WeasyPrint configuration options.
            remove_multimedia (bool): Whether to attempt a fallback cleanup.


        Raises:
            OSError: If weasyprint is missing or weasyprint fails.

        Returns:
            tuple[bool, str | None]:
                - success (bool)
                - optional warning message (str | None)
        """

        logger.info("Starting weasyprint")
        try:
            await asyncio.to_thread(render_pdf_sync, html, css, output_path)
            logger.info("Weasyprint OK into : %s", output_path)
            return True, None

        except OSError as e:
            logger.error("WeasyPrint failed on first attempt: %s", e)

            if not remove_multimedia:
                raise PDFError(f"WeasyPrint failed: {e}") from e

            logger.warning("Retrying after removing multimedia embeds")

            # Remove multimedia blocks
            cleaned_html = HTMLParser(html)
            for node in cleaned_html.css("div.multimedia-embed"):
                node.decompose()
            logger.info("Decomposing some medias-embed")
            logger.info("Retry weasyprint")

            cleaned = cleaned_html.html
            assert cleaned is not None  # invariant: cleaned_html.html is always a string
            try:
                await asyncio.to_thread(render_pdf_sync, cleaned, css, output_path)

                logger.info("2nd attempt weasy print OK")
                return (
                    True,
                    "Multimedia content was removed because weasyprint could not render it.",
                )
            except Exception as e2:
                logger.error("Second attempt failed as well: %s", e2)
                raise PDFError(f"WeasyPrint failed after cleanup: {e2}") from e2

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
            await self.close()
            logger.info("client.close() and pdf_workder.close() OK in __exit__")
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

    async def fetch_comments(self, page_id: str, page: int = 1, limit: int = 20) -> JSONObject:
        url = (
            f"{self.HOST}/ajax/feedbacks/page"
            f"?pageId={page_id}&page={page}&limit={limit}&order=likes"
        )
        resp = await self.client.get(url)
        resp.raise_for_status()
        return resp.json()  # type: ignore


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
            article = lm.fetch_pdf(
                url=URL1, email=email, password=password, mobile=False, dark=True
            )
            print(article.path, article.success, article.warning)
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
            article = await lm.fetch_pdf(
                url=URL2, email=email, password=password, mobile=True, dark=True
            )
            print(article.path, article.success, article.warning)
            # id = lm.extract_page_id(URL2)
            # print(f"Extracted page ID: {id}")
            # json_data = await lm.fetch_comments(page_id=id, page=1, limit=5)
            # comments = [parse_comment(c) for c in json_data["comments"]]
            # for c in comments:
            #     print(c)

    main_context()
    time.sleep(0.5)
    asyncio.run(amain_context())
