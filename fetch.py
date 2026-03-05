# pyright: reportUnusedCallResult=false
import argparse
import logging
import os
import random
import time

import mtc
import qrz
import qth
import rle
import storage
from settings import settings

LOG = logging.getLogger(__name__)

sources = {
    "qth": qth.QTH,
    "qrz": qrz.QRZ,
    "mtc": mtc.MTC,
    "rle": rle.RLE,
}


def ratelimit():
    delay = random.randint(10, 180)
    LOG.info("waiting for %d seconds before next fetch", delay)
    time.sleep(delay)


def parse_args():
    p = argparse.ArgumentParser()

    p.add_argument(
        "--sources",
        "-s",
        help="Comma separated list of sources",
        type=lambda x: x.split(","),
        default=",".join(sources.keys()),
    )

    return p.parse_args()


def main():
    logging.basicConfig(level="INFO")

    args = parse_args()

    store = storage.SqlStorage(settings.database_url)

    for srcname in args.sources:
        src = sources[srcname](store, ratelimit=ratelimit)
        LOG.info("fetching from %s", srcname)
        with store:
            try:
                src.update()
            except Exception as err:
                LOG.warning("stopped processing %s due to error: %s", src.name, err)
            LOG.info(f"found {store.counter} new items")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
