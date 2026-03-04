import datetime

import flask
import tabulate
from feedgen.feed import FeedGenerator

import storage

app = flask.Flask(__name__)


def to_paragraphs(s: str) -> str:
    return "\n".join(f"<p>{line}</p>" for line in s.split("\n\n"))


def build_feed() -> FeedGenerator:
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
        description = ""
        if item.description:
            description = to_paragraphs(item.description)
        description += tabulate.tabulate(mdtable, tablefmt="html")

        if callsign := item.meta.get("callsign"):
            callsign_url = f"https://www.qrz.com/db/{callsign}"
            entry.author(name=callsign, uri=callsign_url, email="invalid@example.com")
            description += f'<p>Author: <a href="{callsign_url}">{callsign}</a></p>'

        entry.content(description, type="html")

        # Some sources provide a posted date, some do not.
        if item.date_posted:
            entry.published(item.date_posted.astimezone(datetime.timezone.utc))
        else:
            entry.published(item.date_added.astimezone(datetime.timezone.utc))

    return feed


@app.get("/rss.xml")
def rss_xml():
    feed = build_feed()
    return feed.rss_str()


@app.get("/atom.xml")
def atom_xml():
    feed = build_feed()
    return feed.atom_str()


if __name__ == "__main__":
    app.run(port=8082)
