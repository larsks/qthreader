import logging
import random
import time

import qth
import storage

LOG = logging.getLogger(__name__)

logging.basicConfig(level="INFO")
store = storage.SqliteStorage("items.db")
q = qth.QTH(store, ratelimit=lambda: time.sleep(random.randint(30, 180)), max_pages=50)

with store:
    new = q.update()
    LOG.info(f"found {store.counter} new items")
