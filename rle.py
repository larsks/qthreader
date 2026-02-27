import logging
import urllib.parse as urlparse
from typing import Callable, Literal, cast

import bs4
import pydantic
import requests

import storage

LOG = logging.getLogger(__name__)


class Item(pydantic.BaseModel):
    link: str
    id: str
    source: Literal["rle"] = "rle"
    title: str
    meta: dict[str, str] = {}


class RLE:
    url: str = "https://www2.randl.com/index.php?main_page=usedbrand"
    store: storage.Storage
    name: str = "mtc"

    def __init__(
        self,
        store: storage.Storage,
        url: str | None = None,
        ratelimit: Callable[[], None] | None = None,
    ):
        self.store = store
        if url:
            self.url = url

    def update(self):
        res = requests.get(self.url)
        res.raise_for_status()
        doc = bs4.BeautifulSoup(res.text, "lxml")
        prods = doc.select("center > table > tr")

        for prod in prods:
            td_vendor, td_title, td_price = prod.select("td")
            title = cast(str, td_title.text).removeprefix("Used ").strip()
            vendor = cast(str, td_vendor.text)
            title = f"{vendor} {title}"
            price = cast(str, td_price.text)
            link = cast(str, td_title.select("a")[0].get("href"))
            link = urlparse.urljoin(self.url, link)
            info = urlparse.parse_qs(urlparse.urlsplit(link).query)
            prodid = info.get("products_id", [""])[0]
            item = Item(link=link, id=prodid, title=title, meta={"price": price})

            try:
                self.store.add(storage.Item.model_validate(item.model_dump()))
            except storage.IntegrityError:
                pass
