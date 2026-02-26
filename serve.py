import datetime

import flask
from feedgen.feed import FeedGenerator

import storage

app = flask.Flask(__name__)


@app.get("/rss.xml")
def rss_xml():
    store = storage.SqliteStorage("items.db")
    feed = FeedGenerator()

    feed.id("https://swap.qth.com/")
    feed.title("QTH Swap Meet")
    feed.description("QTH Swap Meet")
    feed.link(href="https://swap.qth.com/", rel="alternate")
    feed.link(href="http://localhost:8082/rss.xml", rel="self")

    for item in store.items():
        entry = feed.add_entry()
        entry.guid(item.link)
        entry.title(item.title)
        entry.link(href=item.link)
        entry.description(item.description)
        entry.published(item.date_posted.astimezone(datetime.timezone.utc))

    return feed.rss_str()


if __name__ == "__main__":
    app.run(port=8082)
