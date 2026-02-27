import logging
import random
import time

import mtc
import qth
import storage

LOG = logging.getLogger(__name__)


def ratelimit():
    delay = random.randint(10, 180)
    LOG.info("waiting for %d seconds before next fetch", delay)
    time.sleep(delay)


logging.basicConfig(level="INFO")
store = storage.SqliteStorage("items.db")
qth_src = qth.QTH(store, ratelimit=ratelimit)
mtc_src = mtc.MTC(store, ratelimit=ratelimit)

for src in [qth_src, mtc_src]:
    with store:
        try:
            new = src.update()
        except Exception as err:
            LOG.warning("stopped processing %s due to error: %s", src.name, err)
        LOG.info(f"found {store.counter} new items")
