import datetime

import flask
import tabulate
from feedgen.feed import FeedGenerator

import storage

app = flask.Flask(__name__)


@app.get("/rss.xml")
def rss_xml():
    store = storage.SqliteStorage("items.db")
    feed = FeedGenerator()

    feed.id("swapmeet")
    feed.title("Amateur Radio Swap Meet")
    feed.description("Amateur Radio Swap Meet")
    feed.link(href="http://localhost:8082/rss.xml", rel="self")

    for item in store.items():
        entry = feed.add_entry()
        entry.guid(item.link)
        entry.title(f"[{item.source}] {item.title}")
        entry.link(href=item.link)

        mdtable = [["source", item.source]] + [[k, v] for k, v in item.meta.items()]
        entry.description(
            (item.description if item.description else "")
            + "\n\n"
            + tabulate.tabulate(mdtable)
        )

        # Some sources provide a posted date, some do not.
        if item.date_posted:
            entry.published(item.date_posted.astimezone(datetime.timezone.utc))
        else:
            entry.published(item.date_added.astimezone(datetime.timezone.utc))

    return feed.rss_str()


if __name__ == "__main__":
    app.run(port=8082)
