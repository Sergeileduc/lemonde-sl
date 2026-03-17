import asyncio
import os

from dotenv import load_dotenv
from rich import print

from lemonde_sl import LeMonde, LeMondeAsync

# Login credentials
load_dotenv()
email = os.getenv("LM_SL_EMAIL") or ""
password = os.getenv("LM_SL_PASSWD") or ""
URL1 = os.getenv("LM_SL_TEST_URL1") or ""
URL2 = os.getenv("LM_SL_TEST_URL2") or ""


def runsync_one():
    print("Version SYNC")
    with LeMonde() as lm:
        print(lm)
        art = lm.fetch_pdf(
            url=URL1, email=email, password=password, max_img=5
        )  # limit 5 images for no OOM
        print(art)

        # Comments
        # id = lm.extract_page_id(URL1)
        # print(f"Extracted page ID: {id}")
        # json_data = lm.fetch_comments(page_id=id, page=1, limit=5)
        # comments = [parse_comment(c) for c in json_data["comments"]]
        # for c in comments:
        #     print(c)


def runsync_matrix():
    print("Version SYNC")
    with LeMonde() as lm:
        print(lm)
        matrix = ["normal_light", "normal_dark", "mobile_light", "mobile_dark"]
        articles = lm.fetch_multiple_pdf(
            url=URL1, email=email, password=password, matrix=matrix, max_img=5
        )
        for art in articles:
            print(art)

        # Comments
        # id = lm.extract_page_id(URL1)
        # print(f"Extracted page ID: {id}")
        # json_data = lm.fetch_comments(page_id=id, page=1, limit=5)
        # comments = [parse_comment(c) for c in json_data["comments"]]
        # for c in comments:
        #     print(c)


def runsync_all():
    print("Version SYNC")
    with LeMonde() as lm:
        print(lm)
        articles = lm.fetch_all_pdf(url=URL1, email=email, password=password, max_img=5)
        for art in articles:
            print(art)

        # Comments
        # id = lm.extract_page_id(URL1)
        # print(f"Extracted page ID: {id}")
        # json_data = lm.fetch_comments(page_id=id, page=1, limit=5)
        # comments = [parse_comment(c) for c in json_data["comments"]]
        # for c in comments:
        #     print(c)


async def runasync_one():
    async with LeMondeAsync() as lm:
        print(lm)
        article = await lm.fetch_pdf(
            url=URL2, email=email, password=password, mobile=True, dark=True, max_img=5
        )
        print(article)


async def runasync_matrix():
    async with LeMondeAsync() as lm:
        print(lm)
        matrix = ["normal_light", "normal_dark", "mobile_light", "mobile_dark"]
        articles = await lm.fetch_multiple_pdf(
            url=URL2, email=email, password=password, matrix=matrix, max_img=5
        )

        for art in articles:
            print(art)
        #     print(article.path, article.success, article.warning)


async def runasync_all():
    async with LeMondeAsync() as lm:
        print(lm)
        articles = await lm.fetch_all_pdf(url=URL2, email=email, password=password, max_img=5)
        for art in articles:
            print(art)


if __name__ == "__main__":
    import time
    from pathlib import Path

    # CLEAN
    exclude = ("venv", ".venv")
    p = Path(".")
    genpdf = (i for i in p.rglob("*.pdf") if not str(i.parent).startswith(exclude))
    for art in genpdf:
        os.remove(art)

    # Sync
    runsync_one()
    time.sleep(0.5)
    runsync_matrix()
    time.sleep(0.5)
    runsync_all()
    time.sleep(0.5)

    # Async
    asyncio.run(runasync_one())
    time.sleep(0.5)
    asyncio.run(runasync_matrix())
    time.sleep(0.5)
    asyncio.run(runasync_all())
