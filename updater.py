# pyright: reportUnusedCallResult=false
import argparse
import logging
import random
import time
from typing import Callable

import schedule

import mtc
import qrz
import qth
import rle
import storage

LOG = logging.getLogger(__name__)

sources = {
    "qth": qth.QTH,
    "mtc": mtc.MTC,
    "rle": rle.RLE,
}


def ratelimit():
    delay = random.randint(10, 180)
    LOG.info("waiting for %d seconds before next fetch", delay)
    time.sleep(delay)


def wrap_update(source: str, store: storage.Storage, f: Callable[[], None]):
    def func():
        try:
            with store:
                f()
        except storage.IntegrityError as err:
            LOG.warning("caught error from %s: %s", source, err)

        LOG.info("found %d new items", store.getNewItemCount())

    return func


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()

    p.add_argument(
        "--interval",
        "-i",
        action="append",
        type=lambda s: ((parts := s.split("="))[0], int(parts[1])),
    )

    return p.parse_args()


def main():
    args = parse_args()
    intervals = dict(args.interval)
    logging.basicConfig(level="INFO")
    store = storage.SqliteStorage("items.db")

    d_qth = qth.QTH(store, ratelimit=ratelimit)
    d_mtc = mtc.MTC(store, ratelimit=ratelimit)
    d_rle = rle.RLE(store, ratelimit=ratelimit)
    d_qrz = qrz.QRZ(store, ratelimit=ratelimit)

    schedule.every(60).to(120).minutes.do(
        wrap_update("qth", store, d_qth.update),
    )
    schedule.every(60).to(120).minutes.do(
        wrap_update("qrz", store, d_qrz.update),
    )
    schedule.every(interval=720).to(780).minutes.do(
        wrap_update("mtc", store, d_mtc.update),
    )
    schedule.every(interval=720).to(780).minutes.do(
        wrap_update("rle", store, d_rle.update),
    )

    loopcount = 0
    while True:
        idle = schedule.idle_seconds()
        if idle is not None and loopcount % 120 == 0:
            LOG.info("%d seconds until next job runs", idle)
        schedule.run_pending()
        loopcount += 1
        time.sleep(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
