import re
import requests
from bs4 import BeautifulSoup
import openpyxl
from datetime import datetime

# ======================================
# Load Excel file
# ======================================
urls = []
vendors = []
wb = openpyxl.load_workbook("update-list.xlsx", data_only=True)
sheet = wb.active

for row in sheet.iter_rows(min_row=2):
    cell = row[1]
    link = None
    if cell.hyperlink:
        link = cell.hyperlink.target
    elif isinstance(cell.value, str) and cell.value.startswith("http"):
        link = cell.value.strip()

    if link:
        urls.append(link)
        vendors.append(str(row[0].value or "").strip())

# ======================================
# Regex patterns
# ======================================
# Strict contextual pattern (SteelSeries, Brave)
contextual_pattern = re.compile(
    r"""
    (?:\b(?:version|v(?:er)?|build|release|rev(?:ision)?|update|gg)\s*)
    [#:=-]?\s*
    \d+(?:\.\d+){0,3}(?:\.x)?(?:\s*(?:beta|rc|patch)\s*\d*)?\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Fallback for long dotted numbers (Wikipedia style)
long_numeric_pattern = re.compile(r"\b\d+(?:\.\d+){2,4}\b", re.IGNORECASE)

# Date pattern to detect and compare (Brave filtering)
date_pattern = re.compile(
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}",
    re.IGNORECASE,
)


# ======================================
# Utility Functions
# ======================================
def parse_dates_from_context(context):
    """Extract all dates in the text and return the latest one <= today."""
    dates = []
    for match in date_pattern.findall(context):
        try:
            dt = datetime.strptime(match.replace(",", ""), "%B %d %Y")
            dates.append(dt)
        except ValueError:
            # Try short month
            try:
                dt = datetime.strptime(match.replace(",", ""), "%b %d %Y")
                dates.append(dt)
            except ValueError:
                continue
    if not dates:
        return None
    # Return the most recent past date
    past_dates = [d for d in dates if d <= datetime.now()]
    return max(past_dates) if past_dates else None


def is_future_release(context):
    """Check if the version's release date is in the future."""
    for match in date_pattern.findall(context):
        try:
            dt = datetime.strptime(match.replace(",", ""), "%B %d %Y")
            if dt > datetime.now():
                return True
        except ValueError:
            try:
                dt = datetime.strptime(match.replace(",", ""), "%b %d %Y")
                if dt > datetime.now():
                    return True
            except ValueError:
                continue
    return False


# ======================================
# Main scraping loop
# ======================================
output_path = "scraped_versions-v6.txt"
with open(output_path, "w", encoding="utf-8") as file:
    for index, url in enumerate(urls):
        vendor = vendors[index]
        print(f"\n🔍 Fetching {vendor}: {url}")

        try:
            res = requests.get(url, timeout=25)
            res.raise_for_status()
        except Exception as e:
            print(f"❌ Failed to fetch {vendor}: {e}")
            file.write(f"{vendor}\nFAILED TO FETCH: {url}\n\n")
            continue

        soup = BeautifulSoup(res.text, "html.parser")
        text = soup.get_text(separator="\n")
        lines = [l.strip() for l in text.splitlines() if len(l.strip()) > 3]

        matches = []

        for i, line in enumerate(lines):
            # Contextual pattern first
            found = contextual_pattern.search(line)
            if not found:
                # fallback long numeric pattern (Wikipedia)
                found = long_numeric_pattern.search(line)

            if not found:
                continue

            version = found.group()
            context = "\n".join(lines[max(0, i - 2) : i + 3]).lower()

            # Skip obvious junk or future releases
            if any(
                x in context
                for x in [
                    "webview",
                    "edge",
                    "chrome",
                    "android",
                    "ios",
                    "browser",
                    "beta program",
                ]
            ):
                continue
            if is_future_release(context):
                continue

            # Post filter - ignore single-digit versions or JS assets
            if re.fullmatch(r"v?\s*\d{1,2}\b", version, re.IGNORECASE):
                continue
            if "/v" in context:
                continue

            matches.append(version)

        # Deduplicate
        seen = set()
        filtered = [x for x in matches if not (x in seen or seen.add(x))]

        # Write output
        file.write(f"{vendor}\n{'-'*len(vendor)}\n")
        if filtered:
            for item in filtered:
                file.write(item + "\n")
        else:
            file.write("No valid versions found.\n")
        file.write("\n")

print(f"\n✅ File created: {output_path}")
