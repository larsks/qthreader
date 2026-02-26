import datetime
import logging
import re
from typing import Callable, cast

import bs4
import pydantic
import requests

import storage

LOG = logging.getLogger(__name__)

re_listing = re.compile(
    r"""
    (?P<description>.*?)         # Free-form description (non-greedy, includes newlines)
    Listing\s+\#                 # Literal "Listing #" with whitespace
    (?P<id>\d+)                  # Listing number (digits)
    \s+-\s+                      # Space, hyphen, space
    Submitted\s+on\s+            # "Submitted on" with whitespace
    (?P<date_posted>\d\d/\d\d/\d\d)     # Date in dd/mm/yy format
    \s+by\s+Callsign\s+          # "by Callsign" with whitespace
    (?P<callsign>\w+)            # Callsign (non-whitespace chars)
    (
    ,\s+
    Modified\s+on\s+
    (?P<date_modified>\d\d/\d\d/\d\d)     # Date in dd/mm/yy format
    )?
    """,
    re.VERBOSE | re.DOTALL,
)


class Item(pydantic.BaseModel):
    link: str
    title: str
    description: str
    date_posted: datetime.datetime | str
    date_modified: datetime.datetime | str | None = None
    meta: dict[str, str] = {}

    @pydantic.field_validator("date_posted", "date_modified", mode="before")
    @classmethod
    def validate_date(
        cls, val: str | None | datetime.datetime
    ) -> datetime.datetime | None:
        if val is None:
            return
        if type(val) is str:
            dtval = datetime.datetime.strptime(val, "%m/%d/%y")
            return dtval
        elif type(val) is datetime.datetime:
            return val
        else:
            raise ValueError(val)


class QTH:
    url: str = "https://swap.qth.com/all.php"
    max_pages: int = 5
    store: storage.Storage
    ratelimit: Callable[[], None] | None

    def __init__(
        self,
        store: storage.Storage,
        url: str | None = None,
        max_pages: int | None = None,
        ratelimit: Callable[[], None] | None = None,
    ):
        self.store = store
        self.ratelimit = ratelimit

        if url is not None:
            self.url = url

        if max_pages is not None:
            self.max_pages = max_pages

    def make_link(self, item_number: str | int) -> str:
        return f"https://swap.qth.com/view_ad.php?counter={item_number}"

    def get_page(self, n: int):
        LOG.info(f"get page {n}")
        res = requests.get(self.url, params={"page": n})
        res.raise_for_status()
        return res.text

    def extract_items(
        self, content: str, additional_meta: dict[str, str] | None = None
    ) -> None:
        page = bs4.BeautifulSoup(content, "lxml")
        ilist = page.select(".qth-content-wrap dt")

        for item in ilist:
            title = cast(str, item.text).strip()

            # The "all listings" page prefixes the title with the category. We handle both cases
            # here so that the code works with both per-category links as well as with
            # /all.php.
            try:
                _, title = title.split(" - ", 1)
            except ValueError:
                pass

            title = title.strip()
            data = item.next_sibling
            if data:
                mo = re_listing.match(cast(str, data.text).strip())
                if mo:
                    meta = additional_meta if additional_meta else {}
                    meta["callsign"] = mo.group("callsign")
                    item = Item(
                        link=self.make_link(mo.group("id")),
                        title=title,
                        description=mo.group("description"),
                        date_posted=mo.group("date_posted"),
                        date_modified=mo.group("date_modified"),
                        meta=meta,
                    )
                    self.store.add(storage.Item.model_validate(item.model_dump()))
                else:
                    LOG.error("failed to parse listing from %s", item)
                    breakpoint()
                    pass

    def process_page(self, n: int) -> None:
        content = self.get_page(n)
        self.extract_items(content, additional_meta={"page": f"{n}"})

    def update(self) -> None:
        pageno = 1

        while pageno <= self.max_pages:
            self.process_page(pageno)
            pageno += 1
            if self.ratelimit:
                self.ratelimit()
