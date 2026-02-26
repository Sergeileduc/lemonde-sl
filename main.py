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


def runsync():
    print("Version SYNC")
    with LeMonde() as lm:
        # print(lm)
        # lm.fetch_pdf(url=URL1, email=email, password=password, mobile=True, dark=True)
        # matrix = ["normal_light", "normal_dark", "mobile_light", "mobile_dark"]
        # lm.fetch_multiple_pdf(url=URL1, email=email, password=password, matrix=matrix)
        lm.fetch_all_pdf(url=URL1, email=email, password=password)
        # id = lm.extract_page_id(URL1)
        # print(f"Extracted page ID: {id}")
        # json_data = lm.fetch_comments(page_id=id, page=1, limit=5)
        # comments = [parse_comment(c) for c in json_data["comments"]]
        # for c in comments:
        #     print(c)


async def runasync():
    async with LeMondeAsync() as lm:
        print(lm)
        # article = await lm.fetch_pdf(
        #     url=URL2, email=email, password=password, mobile=True, dark=True
        # )
        # print(article.path, article.success, article.warning)
        # matrix = ["normal_light", "normal_dark", "mobile_light", "mobile_dark"]
        # articles = await lm.fetch_multiple_pdf(
        #     url=URL2, email=email, password=password, matrix=matrix
        # )

        # for article in articles:
        #     print(article.path, article.success, article.warning)

        await lm.fetch_all_pdf(url=URL2, email=email, password=password)


if __name__ == "__main__":
    import time

    runsync()
    time.sleep(0.5)
    asyncio.run(runasync())
