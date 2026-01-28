import os

from dotenv import load_dotenv
from rich import print

from lemonde_sl import LeMonde, parse_comment

# Login credentials
load_dotenv()
email = os.getenv("LM_SL_EMAIL") or ""
password = os.getenv("LM_SL_PASSWD") or ""
URL1 = os.getenv("LM_SL_TEST_URL1") or ""
URL2 = os.getenv("LM_SL_TEST_URL2") or ""

print("Version SYNC")
with LeMonde() as lm:
    print(lm)
    lm.fetch_pdf(url=URL1, email=email, password=password)
    id = lm.extract_page_id(URL1)
    print(f"Extracted page ID: {id}")
    json_data = lm.fetch_comments(page_id=id, page=1, limit=5)
    comments = [parse_comment(c) for c in json_data["comments"]]
    for c in comments:
        print(c)
