# pyright: reportUnusedCallResult=false

import argparse
import logging
import random
import time
from typing import Callable, Protocol

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


class Driver(Protocol):
    def update(self): ...


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

        LOG.info("found %d new items from %s", store.getNewItemCount(), source)

    return func


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()

    p.add_argument(
        "--interval",
        "-i",
        action="append",
        default=[],
        type=lambda s: ((parts := s.split("="))[0], int(parts[1])),
    )

    p.add_argument(
        "--jitter",
        "-j",
        type=float,
        default=0.5,
    )

    p.add_argument(
        "--source",
        "-s",
        action="append",
    )

    p.add_argument(
        "--immediately",
        "-I",
        action="store_true",
    )

    return p.parse_args()


def schedule_with_jitter(func, interval: int, jitter: float = 0.5):
    low = int(interval - (interval * jitter))
    high = int(interval + (interval * jitter))

    if low <= 0:
        raise ValueError(f"interval {interval} with jitter {jitter} must be > 0")
    schedule.every(low).to(high).minutes.do(func)


def main():
    args = parse_args()
    intervals: dict[str, int] = dict(args.interval)
    logging.basicConfig(level="INFO")
    store = storage.SqliteStorage("items.db")

    drivers: dict[str, tuple[Driver, int]] = {
        "qth": (qth.QTH(store, ratelimit=ratelimit), 60),
        "mtc": (mtc.MTC(store, ratelimit=ratelimit), 720),
        "rle": (rle.RLE(store, ratelimit=ratelimit), 720),
        "qrz": (qrz.QRZ(store, ratelimit=ratelimit), 60),
    }

    for name, (driver, default_interval) in drivers.items():
        if args.source is None or name in args.source:
            schedule_with_jitter(
                wrap_update(name, store, driver.update),
                intervals.get(name, default_interval),
                jitter=args.jitter,
            )

    if args.immediately:
        for name, (driver, default_interval) in drivers.items():
            wrap_update(name, store, driver.update)()

    loopcount = 0
    while True:
        idle = schedule.idle_seconds()
        if idle is not None and loopcount % 300 == 0:
            LOG.info("%d seconds until next job runs", idle)
        schedule.run_pending()
        loopcount += 1
        time.sleep(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
