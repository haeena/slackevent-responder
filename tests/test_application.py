import json
import time

from freezegun import freeze_time
from starlette.testclient import TestClient

from slackevent_responder import SlackEventApp

from .helpers.helpers import create_signature


class TestSignature:
    def test_verify_signature(self, verify_signatures_fixture):
        # setup
        (
            expected,
            signing_secret,
            timestamp,
            data,
            signature,
        ) = verify_signatures_fixture
        app = SlackEventApp(slack_signing_secret=signing_secret)

        # run
        result = app.verify_signature(
            timestamp=timestamp, request_body=data, signature=signature
        )

        # validate
        assert result == expected


class TestEndpoint:
    def test_get(self, app, signing_secret, slack_event_path):
        # setup
        client = TestClient(app)

        # run
        response = client.get(slack_event_path)

        # validate
        assert (
            response.text == "These are not the slackbots you're looking for."
        )
        assert response.status_code == 404

    def test_no_timestamp(self, app, signing_secret, slack_event_path):
        # setup
        client = TestClient(app)
        headers = {}

        # run
        response = client.post(slack_event_path, headers=headers)

        # validate
        assert response.text == "Request doesn't contain timestamp header"
        assert response.status_code == 403

    @freeze_time("2013-08-14")
    def test_invalid_before_timestamp(
        self, app, signing_secret, slack_event_path
    ):
        # setup
        client = TestClient(app)
        headers = {
            "X-Slack-Request-Timestamp": str(int(time.time() - 60 * 5 - 1))
        }

        # run
        response = client.post(slack_event_path, headers=headers)

        # validate
        assert response.text == "Invalid timestamp in request header"
        assert response.status_code == 403

    @freeze_time("2013-08-14")
    def test_invalid_after_timestamp(
        self, app, signing_secret, slack_event_path
    ):
        # setup
        client = TestClient(app)
        headers = {
            "X-Slack-Request-Timestamp": str(int(time.time() + 60 * 5 + 1))
        }

        # run
        response = client.post(slack_event_path, headers=headers)

        # validate
        assert response.text == "Invalid timestamp in request header"
        assert response.status_code == 403

    @freeze_time("2013-08-14")
    def test_invalid_signature(self, app, signing_secret, slack_event_path):
        # setup
        client = TestClient(app)
        timestamp = str(int(time.time()))
        headers = {
            "X-Slack-Request-Timestamp": timestamp,
            "X-Slack-Signature": "",
        }

        # run
        response = client.post(slack_event_path, headers=headers)

        # validate
        assert response.text == "Invalid request signature"
        assert response.status_code == 403

    @freeze_time("2013-08-14")
    def test_challenge(
        self, app, signing_secret, slack_event_path, url_challenge_fixture
    ):
        # setup
        client = TestClient(app)
        timestamp = str(int(time.time()))
        json_data = url_challenge_fixture
        data = json.dumps(json_data)
        signature = create_signature(signing_secret, timestamp, data)
        headers = {
            "X-Slack-Request-Timestamp": timestamp,
            "X-Slack-Signature": signature,
        }

        # run
        response = client.post(slack_event_path, data=data, headers=headers)

        # validate
        assert response.text == json_data["challenge"]
        assert response.status_code == 200

    @freeze_time("2013-08-14")
    def test_event(
        self, app, signing_secret, slack_event_path, reaction_event_fixture
    ):
        # setup
        client = TestClient(app)
        timestamp = str(int(time.time()))
        json_data = reaction_event_fixture
        data = json.dumps(json_data)
        signature = create_signature(signing_secret, timestamp, data)
        headers = {
            "X-Slack-Request-Timestamp": timestamp,
            "X-Slack-Signature": signature,
        }

        # run
        response = client.post(slack_event_path, data=data, headers=headers)

        # validate
        assert response.text == ""
        assert response.status_code == 200
        assert "X-Slack-Powered-By" in response.headers

    @freeze_time("2013-08-14")
    def test_no_event(
        self, app, signing_secret, slack_event_path, reaction_event_fixture
    ):
        # setup
        client = TestClient(app)
        timestamp = str(int(time.time()))
        json_data = reaction_event_fixture
        json_data.pop("event")
        data = json.dumps(json_data)
        signature = create_signature(signing_secret, timestamp, data)
        headers = {
            "X-Slack-Request-Timestamp": timestamp,
            "X-Slack-Signature": signature,
        }

        # run
        response = client.post(slack_event_path, data=data, headers=headers)

        # validate
        assert response.text == "No event in request body"
        assert response.status_code == 403

    @freeze_time("2013-08-14")
    def test_no_event_type(
        self, app, signing_secret, slack_event_path, reaction_event_fixture
    ):
        # setup
        client = TestClient(app)
        timestamp = str(int(time.time()))
        json_data = reaction_event_fixture
        json_data["event"].pop("type")
        data = json.dumps(json_data)
        signature = create_signature(signing_secret, timestamp, data)
        headers = {
            "X-Slack-Request-Timestamp": timestamp,
            "X-Slack-Signature": signature,
        }

        # run
        response = client.post(slack_event_path, data=data, headers=headers)

        # validate
        assert response.text == "No event in request body"
        assert response.status_code == 403


class TestEventHandler:
    def test_handlers_zero(self, app):
        # setup
        event_type = "something"

        # run
        handlers = app.handlers(event_type)

        # validate
        assert len(handlers) == 0

    def test_handlers_one(self, app):
        # setup
        event_type = "something"

        # run
        @app.on(event_type)
        def handler(event_data):
            pass

        handlers = app.handlers(event_type)

        # validate
        assert len(handlers) == 1
        assert handlers[0] == handler

    def test_handlers_multi(self, app):
        # setup
        event_type = "something"

        # run
        @app.on(event_type)
        def handler1(event_data):
            pass

        @app.once(event_type)
        async def handler2(event_data):
            pass

        handlers = app.handlers(event_type)

        # validate
        assert len(handlers) == 2
        assert handler1 in handlers
        assert handler2 in handlers

    def test_remove_handler(self, app):
        # setup
        event_type = "something"

        @app.on(event_type)
        def handler1(event_data):
            pass

        @app.once(event_type)
        def handler2(event_data):
            pass

        # run
        app.remove_handler(event_type, handler1)

        # validate
        handlers = app.handlers(event_type)
        assert len(handlers) == 1
        assert handlers[0] == handler2

    def test_remove_all_handlers_for_a_event(self, app):
        # setup
        event_type = "something"

        @app.on(event_type)
        def handler1(event_data):
            pass

        @app.once(event_type)
        def handler2(event_data):
            pass

        # run
        app.remove_all_handlers(event_type)

        # validate
        handlers = app.handlers(event_type)
        assert len(handlers) == 0

    def test_remove_all_handlers_for_all_event(self, app):
        # setup
        event_type1 = "foo"

        @app.on(event_type1)
        def handler1(event_data):
            pass

        event_type2 = "bar"

        @app.once(event_type2)
        def handler2(event_data):
            pass

        # run
        app.remove_all_handlers()

        # validate
        handlers1 = app.handlers(event_type1)
        assert len(handlers1) == 0
        handlers2 = app.handlers(event_type2)
        assert len(handlers2) == 0

    @freeze_time("2013-08-14")
    def test_run_handler_on_sync(
        self, app, signing_secret, slack_event_path, reaction_event_fixture
    ):
        # setup
        client = TestClient(app)
        timestamp = str(int(time.time()))
        json_data = reaction_event_fixture
        event_type = json_data["event"]["type"]
        data = json.dumps(json_data)
        signature = create_signature(signing_secret, timestamp, data)
        headers = {
            "X-Slack-Request-Timestamp": timestamp,
            "X-Slack-Signature": signature,
        }

        EVENT_DATA_IN_HANDLER = None

        # run
        @app.on(event_type)
        def handler(event_data):
            nonlocal EVENT_DATA_IN_HANDLER
            EVENT_DATA_IN_HANDLER = event_data

        client.post(slack_event_path, data=data, headers=headers)

        # validate
        assert EVENT_DATA_IN_HANDLER == json_data

    @freeze_time("2013-08-14")
    def test_run_handler_on_async(
        self, app, signing_secret, slack_event_path, reaction_event_fixture
    ):
        # setup
        client = TestClient(app)
        timestamp = str(int(time.time()))
        json_data = reaction_event_fixture
        event_type = json_data["event"]["type"]
        data = json.dumps(json_data)
        signature = create_signature(signing_secret, timestamp, data)
        headers = {
            "X-Slack-Request-Timestamp": timestamp,
            "X-Slack-Signature": signature,
        }

        EVENT_DATA_IN_HANDLER = None

        # run
        @app.on(event_type)
        async def handler(event_data):
            nonlocal EVENT_DATA_IN_HANDLER
            EVENT_DATA_IN_HANDLER = event_data

        client.post(slack_event_path, data=data, headers=headers)

        # validate
        assert EVENT_DATA_IN_HANDLER == json_data

    @freeze_time("2013-08-14")
    def test_run_handler_once_sync(
        self, app, signing_secret, slack_event_path, reaction_event_fixture
    ):
        # setup
        client = TestClient(app)
        timestamp = str(int(time.time()))
        json_data = reaction_event_fixture
        event_type = json_data["event"]["type"]
        data = json.dumps(json_data)
        signature = create_signature(signing_secret, timestamp, data)
        headers = {
            "X-Slack-Request-Timestamp": timestamp,
            "X-Slack-Signature": signature,
        }

        EVENT_DATA_IN_HANDLER = None

        # run
        @app.once(event_type)
        def handler(event_data):
            nonlocal EVENT_DATA_IN_HANDLER
            EVENT_DATA_IN_HANDLER = event_data

        client.post(slack_event_path, data=data, headers=headers)

        # validate
        assert EVENT_DATA_IN_HANDLER == json_data

    @freeze_time("2013-08-14")
    def test_run_handler_once_async(
        self, app, signing_secret, slack_event_path, reaction_event_fixture
    ):
        # setup
        client = TestClient(app)
        timestamp = str(int(time.time()))
        json_data = reaction_event_fixture
        event_type = json_data["event"]["type"]
        data = json.dumps(json_data)
        signature = create_signature(signing_secret, timestamp, data)
        headers = {
            "X-Slack-Request-Timestamp": timestamp,
            "X-Slack-Signature": signature,
        }

        EVENT_DATA_IN_HANDLER = None

        # run
        @app.once(event_type)
        async def handler(event_data):
            nonlocal EVENT_DATA_IN_HANDLER
            EVENT_DATA_IN_HANDLER = event_data

        client.post(slack_event_path, data=data, headers=headers)

        # validate
        assert EVENT_DATA_IN_HANDLER == json_data
