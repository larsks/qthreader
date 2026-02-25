import datetime
import logging
import re
from typing import cast

import bs4
import pydantic
import requests
from feedgen.feed import FeedGenerator
from flask import Flask, abort

LOG = logging.getLogger()

re_listing = re.compile(
    r"""
    (?P<description>.*?)         # Free-form description (non-greedy, includes newlines)
    Listing\s+\#                 # Literal "Listing #" with whitespace
    (?P<number>\d+)              # Listing number (digits)
    \s+-\s+                      # Space, hyphen, space
    Submitted\s+on\s+            # "Submitted on" with whitespace
    (?P<date>\d\d/\d\d/\d\d)     # Date in dd/mm/yy format
    \s+by\s+Callsign\s+          # "by Callsign" with whitespace
    (?P<callsign>\w+)            # Callsign (non-whitespace chars)
    """,
    re.VERBOSE | re.DOTALL,
)

app = Flask(__name__)
feed: FeedGenerator | None = None


class Item(pydantic.BaseModel):
    title: str
    description: str
    number: str
    callsign: str
    date_posted: datetime.datetime | str

    @pydantic.field_validator("date", mode="before")
    @classmethod
    def validate_date(cls, val: str | datetime.datetime) -> datetime.datetime:
        if type(val) is str:
            dtval = datetime.datetime.strptime(val, "%m/%d/%y")
            return dtval
        elif type(val) is datetime.datetime:
            return val
        else:
            raise ValueError(val)

    def callsign_url(self) -> str:
        return f"https://www.qth.com/callsign.php?cs={self.callsign}"

    def item_url(self) -> str:
        return f"https://swap.qth.com/view_ad.php?counter={self.number}"


class QTH:
    url: str = "https://swap.qth.com/all.php"
    max_pages: int = 50

    def __init__(self, url: str | None = None, max_pages: int | None = None):
        if url is not None:
            self.url = url

        if max_pages is not None:
            self.max_pages = max_pages

    def get_page(self, n: int):
        LOG.info(f"get page {n}")
        res = requests.get(self.url, params={"page": n})
        res.raise_for_status()
        return res.text

    def extract_items(self, content: str) -> list[Item]:
        page = bs4.BeautifulSoup(content, "lxml")
        ilist = page.select(".qth-content-wrap dt")
        items: list[Item] = []

        for item in ilist:
            title = cast(str, item.text).strip()
            _, title = title.split(" - ", 1)
            data = item.next_sibling
            if data:
                mo = re_listing.match(cast(str, data.text).strip())
                if mo:
                    items.append(Item(title=title, **mo.groupdict()))

        return items

    def get_items_from_page(self, n: int) -> list[Item]:
        content = self.get_page(n)
        return self.extract_items(content)

    def get_items(self):
        pageno = 1
        items: list[Item] = []

        while pageno <= self.max_pages:
            page_items = self.get_items_from_page(pageno)
            items.extend(page_items)
            pageno += 1

        return items


def build_feed(items: list[Item]) -> FeedGenerator:
    fg = FeedGenerator()
    fg.id("https://swap.qth.com/")
    fg.title("QTH Swap Meet")
    fg.link(href="https://swap.qth.com/", rel="alternate")
    fg.description("HAM Radio Classified Ads")

    # Looks like entries get added to the top of the feed, so process
    # them in reverse to preserve chronological order.
    for item in reversed(items):
        entry = fg.add_entry()
        entry.guid(item.item_url(), permalink=True)
        entry.title(item.title)
        entry.link(href=item.item_url())
        entry.description(item.description)

    return fg


@app.route("/rss.xml")
def rss() -> str:
    if feed is None:
        abort(404)
    return feed.rss_str()


def main():
    global feed
    logging.basicConfig(level="INFO")
    qth = QTH()
    items = qth.get_items()
    feed = build_feed(items)
    app.run(port=8080)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
