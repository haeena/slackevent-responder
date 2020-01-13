import random
import unicodedata

import pytest

from slackevent_responder import SlackEventApp

from .helpers.helpers import create_signature, load_event_fixture


@pytest.fixture(scope="session")
def signing_secret():
    # I'm not completely sure, but it seems to be something like...
    ss_letters = "0123456789abcdef"
    ss_length = 32

    signing_secret = "".join(
        random.choice(ss_letters) for i in range(ss_length)
    )
    return signing_secret


@pytest.fixture(scope="session")
def slack_event_path():
    return "/slack/events"


@pytest.fixture(scope="function")
def app(signing_secret, slack_event_path):
    app = SlackEventApp(
        slack_signing_secret=signing_secret, path=slack_event_path
    )
    return app


@pytest.fixture(scope="session", params=["correct", "incorrect"])
def verify_signatures_fixture(request, signing_secret):
    if request.param == "incorrect":
        return (
            False,
            "",
            "",
            "",
            "v0=0000000000000000000000000000000000000000000000000000000000000000",
        )

    # randomize
    unicode_glyphs = "".join(
        chr(c)
        for c in range(65533)
        # use the unicode categories that don't include control codes
        if unicodedata.category(chr(c))[0] in ("LMNPSZ")
    )
    max_data_length = 1024

    timestamp = str(random.randint(0, 2 ** 31 - 1))
    data = "".join(
        random.choice(unicode_glyphs)
        for i in range(random.randint(0, max_data_length))
    )
    request_signature = create_signature(signing_secret, timestamp, data)
    return (True, signing_secret, timestamp, data, request_signature)


@pytest.fixture
def reaction_event_fixture():
    return load_event_fixture("reaction_added", as_string=False)


@pytest.fixture
def url_challenge_fixture():
    return load_event_fixture("url_challenge", as_string=False)
