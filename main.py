import re
import requests
from bs4 import BeautifulSoup
import openpyxl

urls = []
vendors = []
wb = openpyxl.load_workbook("./update-list.xlsx", data_only=True)
sheet = wb.active
for row in sheet.iter_rows(min_row=2):  # pyright: ignore[reportOptionalMemberAccess]
    urls.append(row[1].hyperlink.target)  # pyright: ignore[reportOptionalMemberAccess]
    vendors.append(row[0].value)

for index, url in enumerate(urls):
    try:
        res = requests.get(url)
        res.raise_for_status()
    except Exception as e:
        print("Failed to fetch url for " + vendors[index])

    soup = BeautifulSoup(
        res.text, "html.parser"  # pyright: ignore[reportPossiblyUnboundVariable]
    )
    text = soup.get_text(separator="\n")

    lines = text.splitlines()

    pattern = re.compile(
        r"""(?:\b(?:version|v(?:er)?|build|release|rev(?:ision)?|update)\s*)[#:=]?\s*\d+(?:\.\d+){0,3}(?:\s*(?:beta|rc|patch)\s*\d*)?\b""",
        re.IGNORECASE | re.VERBOSE,
    )

    matches = []

    for i, line in enumerate(lines):
        if pattern.search(line):
            context = "\n".join(lines[max(0, i - 2) : i + 3])
            if any(
                x in context.lower()
                for x in ["webview", "edge", "chrome", "browser", "android", "ios"]
            ):
                continue
            matches.append(
                pattern.search(
                    line
                ).group()  # pyright: ignore[reportOptionalMemberAccess]
            )

    seen = set()
    filtered = [x for x in matches if not (x in seen or seen.add(x))]

    filePath = "scraped_versions-v5.txt"

    with open(filePath, "a") as file:
        file.write(vendors[index] + "\n")
        for item in filtered:
            file.write(item + "\n")

print("File created!")
