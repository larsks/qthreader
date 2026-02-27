import logging
from typing import Callable, Literal, cast

import bs4
import pydantic
import requests

import storage

LOG = logging.getLogger(__name__)


class Item(pydantic.BaseModel):
    link: str
    id: str
    source: Literal["mtc"] = "mtc"
    title: str
    meta: dict[str, str] = {}


class MTC:
    url: str = "https://mtcradio.com/products/used-gear"
    store: storage.Storage
    ratelimit: Callable[[], None] | None
    name: str = "mtc"

    def __init__(
        self,
        store: storage.Storage,
        url: str | None = None,
        ratelimit: Callable[[], None] | None = None,
    ):
        self.store = store
        if ratelimit:
            self.ratelimit = ratelimit
        if url:
            self.url = url

    def process_batch(self, offset: int) -> int:
        LOG.info("fetching from offset %d", offset)

        res = requests.get(self.url, params={"offset": offset})
        res.raise_for_status()
        doc = bs4.BeautifulSoup(res.text, "lxml")

        items = doc.select(".grid-product")

        for prod in items:
            e_title = prod.select("a.grid-product__title")[0]

            link = cast(str, e_title.get("href"))
            title = cast(str, e_title.text)
            id, title = title.split(None, 1)
            title = title.removeprefix("Used ").removeprefix("AS IS ")
            price = cast(str, prod.select(".grid-product__price-amount")[0].text)

            item = Item(link=link, id=id, title=title, meta={"price": price})
            try:
                self.store.add(storage.Item.model_validate(item.model_dump()))
            except storage.IntegrityError:
                pass

        return len(items)

    def update(self):
        offset = 0
        while True:
            found = self.process_batch(offset)
            if found == 0:
                break

            offset += found
            if self.ratelimit:
                self.ratelimit()
