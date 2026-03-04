"""QRZ RSS feed driver for ham radio gear for sale."""

import datetime
import logging
import os
import re
from enum import Enum
from typing import Any, Callable, Literal, Self, cast
from urllib.parse import urljoin

import feedparser
import pydantic
import requests
from bs4 import BeautifulSoup

import storage

LOG = logging.getLogger(__name__)


class Item(pydantic.BaseModel):
    link: str
    id: str
    source: Literal["qrz"] = "qrz"
    title: str
    description: str | None = None
    date_posted: datetime.datetime | str
    date_modified: datetime.datetime | str | None = None
    meta: dict[str, str] = {}

    @classmethod
    def from_entry(cls, entry: feedparser.FeedParserDict) -> Self:
        return cls(
            title=entry.title,
            link=entry.link,
            id=entry.id,
            date_posted=datetime.datetime(*entry.published_parsed[:6]),
        )


class QRZ:
    """QRZ RSS feed scraper for ham radio gear for sale."""

    name: str = "qrz"
    session: requests.Session
    username: str | None
    password: str | None
    authenticated: bool
    store: storage.Storage

    login_url = "https://www.qrz.com/login"
    rss_url = (
        "https://forums.qrz.com/index.php?forums/ham-radio-gear-for-sale.7/index.rss"
    )

    def __init__(
        self,
        store: storage.Storage,
        session: requests.Session | None = None,
        username: str | None = None,
        password: str | None = None,
        login_url: str | None = None,
        rss_url: str | None = None,
        ratelimit: Callable[[], None] | None = None,
    ):
        self.store = store

        if session:
            self.session = session
        else:
            self.session = requests.Session()

        if login_url:
            self.login_url = login_url

        if rss_url:
            self.rss_url = rss_url

        self.username = username or os.getenv("QRZ_USERNAME")
        self.password = password or os.getenv("QRZ_PASSWORD")
        self.authenticated = False

    def _authenticate(self) -> bool:
        """Authenticate with QRZ login form."""
        if self.authenticated:
            return True

        # Check if credentials are provided
        if not self.username or not self.password:
            LOG.info("missing QRZ credentials")
            return False

        try:
            # First, get the login page to establish a session
            login_page_response = self.session.get(self.login_url)
            login_page_response.raise_for_status()

            doc = BeautifulSoup(login_page_response.text, "lxml")

            # Find the login form
            login_form = doc.find("form")
            if not login_form:
                LOG.error("Could not find login form")
                return False

            # Get the correct form action
            form_action = cast(str, login_form.get("action", "/login"))
            if form_action.startswith("//"):
                login_url = f"https:{form_action}"
            elif form_action.startswith("/"):
                login_url = urljoin(self.login_url, form_action)
            else:
                login_url = form_action

            # Extract all form fields
            form_data: dict[str, str] = {}
            inputs = login_form.find_all("input")

            for inp in inputs:
                input_name = cast(str, inp.get("name"))
                input_type = cast(str, inp.get("type", "text"))
                input_value = cast(str, inp.get("value", ""))

                if input_name:
                    if input_name == "username":
                        form_data[input_name] = self.username
                    elif input_name == "password":
                        form_data[input_name] = self.password
                    elif input_type.lower() in ["hidden", "checkbox"]:
                        form_data[input_name] = input_value

            # Submit the login form
            login_response = self.session.post(
                login_url, data=form_data, allow_redirects=True
            )
            login_response.raise_for_status()

            # Check if login was successful by looking for error messages
            # QRZ shows specific error messages for failed logins
            response_text_lower = login_response.text.lower()

            # Check for specific QRZ error messages
            error_indicators = [
                "no user found with the argument",
                "we could not log you in",
                "login failed",
                "invalid username",
                "invalid password",
                "incorrect username",
                "incorrect password",
            ]

            login_failed = any(
                error in response_text_lower for error in error_indicators
            )

            if login_failed:
                LOG.error("qrz authentication failed")
                return False
            else:
                # No error messages found, assume success
                self.authenticated = True
                LOG.info("qrz authentication successful")
                return True

        except Exception as e:
            LOG.error(f"error during QRZ authentication: {e}")
            return False

    def update(self) -> None:
        if not self._authenticate():
            return

        res = self.session.get(self.rss_url)
        res.raise_for_status()
        feed = feedparser.parse(res.text)

        for entry in feed.entries:
            item = Item.from_entry(entry)
            self.store.add(storage.Item.model_validate(item.model_dump()))
