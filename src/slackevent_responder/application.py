import asyncio
import hashlib
import hmac
import json
import platform
import sys
from collections import OrderedDict, defaultdict
from time import time
from typing import Any, Callable, Dict, Hashable, List, Union

from starlette.background import BackgroundTasks
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route, Router

from .version import __version__


class SlackEventApp(Router):
    def __init__(
        self,
        slack_signing_secret: str,
        slack_event_path: str = "/slack/events",
        **kwargs: Any,
    ):
        self.slack_event_path = slack_event_path
        self._slack_signing_secret = slack_signing_secret
        self._handlers: Dict[
            Hashable, Dict[Callable[..., Any], Callable[..., Any]]
        ] = defaultdict(OrderedDict)
        self._package_info = self._get_package_info()

        super().__init__(
            routes=[
                Route(slack_event_path, self.endpoint, methods=["GET", "POST"])
            ]
        )

    def _get_package_info(self) -> str:
        client_name = __name__.split(".")[0]
        client_version = __version__

        # Collect the package info, Python version and OS version.
        package_info = {
            "client": f"{client_name}/{client_version}",
            "python": "Python/{v.major}.{v.minor}.{v.micro}".format(
                v=sys.version_info
            ),
            "system": "{}/{}".format(platform.system(), platform.release()),
        }

        # Concatenate and format the user-agent string to be passed into request headers
        ua_string = []
        for _key, val in package_info.items():
            ua_string.append(val)

        return " ".join(ua_string)

    def verify_signature(
        self, timestamp: str, request_body: str, signature: str
    ) -> bool:
        # Verify the request signature of the request sent from Slack
        # Generate a new hash using the app's signing secret and request data
        req = f"v0:{timestamp}:{request_body}"

        hexdigest = hmac.new(
            self._slack_signing_secret.encode(), req.encode(), hashlib.sha256
        ).hexdigest()
        request_hash = f"v0={hexdigest}"

        return hmac.compare_digest(request_hash, signature)

    async def endpoint(self, request: Request) -> Response:
        # If requested method is not POST, return 404.
        if request.method != "POST":
            return Response(
                content="These are not the slackbots you're looking for.",
                media_type="text/plain",
                status_code=404,
            )

        # Each request must comes with request timestamp
        request_timestamp = request.headers.get("X-Slack-Request-Timestamp")
        if request_timestamp is None:
            slack_exception = SlackEventAppException(
                "Request doesn't contain timestamp header"
            )
            tasks = self._tasks_from_event("error", slack_exception)
            return Response(
                content="Request doesn't contain timestamp header",
                media_type="text/plain",
                status_code=403,
                background=tasks,
            )

        # Emit an error if the timestamp is out of range
        if abs(time() - int(request_timestamp)) > 60 * 5:
            slack_exception = SlackEventAppException(
                "Invalid timestamp in request header"
            )
            tasks = self._tasks_from_event("error", slack_exception)
            return Response(
                content="Invalid timestamp in request header",
                media_type="text/plain",
                status_code=403,
                background=tasks,
            )

        # Verify the request signature using the app's signing secret
        # emit an error if the signature can't be verified
        request_signature = request.headers.get("X-Slack-Signature", "")
        request_body_bytes = await request.body()
        request_body = request_body_bytes.decode()
        if not self.verify_signature(
            request_timestamp, request_body, request_signature
        ):
            slack_exception = SlackEventAppException(
                "Invalid request signature"
            )
            tasks = self._tasks_from_event("error", slack_exception)
            return Response(
                content="Invalid request signature",
                media_type="text/plain",
                status_code=403,
                background=tasks,
            )

        # Parse the request payload into JSON
        event_data = json.loads(request_body)

        # Echo the URL verification challenge code back to Slack
        if "challenge" in event_data:
            event_type = "challenge"
            tasks = self._tasks_from_event(event_type, event_data)
            return Response(
                content=event_data["challenge"],
                media_type="application/json",
                status_code=200,
                background=tasks,
            )

        # Parse the Event payload and schedule handlers to background tasks
        if "event" in event_data and "type" in event_data["event"]:
            event_type = event_data["event"]["type"]
            tasks = self._tasks_from_event(event_type, event_data)
            response = Response(content="", status_code=200, background=tasks)
            response.headers["X-Slack-Powered-By"] = self._package_info
            return response

        slack_exception = SlackEventAppException("No event in request body")
        tasks = self._tasks_from_event("error", slack_exception)
        return Response(
            content="No event in request body",
            media_type="text/plain",
            status_code=403,
            background=tasks,
        )

    def on(
        self, event: Hashable, f: Callable[..., Any] = None
    ) -> Union[
        Callable[..., Any], Callable[[Callable[..., Any]], Callable[..., Any]]
    ]:
        def _on(f: Callable[..., Any]) -> Callable[..., Any]:
            self._add_handler(event, f, f)
            return f

        if f is None:
            return _on
        else:
            return _on(f)

    def once(
        self, event: Hashable, f: Callable[..., Any] = None
    ) -> Union[
        Callable[..., Any], Callable[[Callable[..., Any]], Callable[..., Any]]
    ]:
        def _wrapper(f: Callable[..., Any]) -> Callable[..., Any]:
            if asyncio.iscoroutinefunction(f):

                async def asyncg(*args: Any, **kwargs: Any) -> Any:
                    self.remove_handler(event, f)
                    return await f(*args, **kwargs)

                self._add_handler(event, f, asyncg)
                return f
            else:

                def g(*args: Any, **kwargs: Any) -> Any:
                    self.remove_handler(event, f)
                    return f(*args, **kwargs)

                self._add_handler(event, f, g)
                return f

        if f is None:
            return _wrapper
        else:
            return _wrapper(f)

    def _add_handler(
        self, event: Hashable, k: Callable[..., Any], v: Callable[..., Any]
    ) -> None:
        self._handlers[event][k] = v

    def _tasks_from_event(
        self, event: Hashable, *args: Any, **kwargs: Any
    ) -> BackgroundTasks:
        tasks = BackgroundTasks()
        for f in list(self._handlers[event].values()):
            tasks.add_task(f, *args, **kwargs)

        return tasks

    def remove_handler(self, event: Hashable, f: Callable[..., Any]) -> None:
        self._handlers[event].pop(f)

    def remove_all_handlers(self, event: Hashable = None) -> None:
        if event is not None:
            self._handlers[event] = {}
        else:
            self._handlers = defaultdict(OrderedDict)

    def handlers(self, event: Hashable) -> List[Callable[..., Any]]:
        return list(self._handlers[event].keys())


class SlackEventAppException(Exception):
    """
    Base exception for all errors raised by the SlackEventHandler library
    """

    def __init__(self, msg: str = None):
        if msg is None:
            # default error message
            msg = "An error occurred in the SlackEventHandler library"
        super().__init__(msg)
