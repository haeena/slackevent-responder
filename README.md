# SlackEvent Responder

[![Test Status](https://github.com/haeena/slackevent-responder/workflows/Test/badge.svg)](https://github.com/haeena/slackevent-responder/actions)
[![codecov](https://codecov.io/gh/haeena/slackevent-responder/branch/master/graph/badge.svg)](https://codecov.io/gh/haeena/slackevent-responder)
[![GitHub license](https://img.shields.io/github/license/haeena/slackevent-responder)](https://github.com/haeena/slackevent-responder/blob/master/LICENSE)

## Introduction

The SlackEvents Responder is an ASGI adapter for [Slack’s Events API](https://api.slack.com/events-api) based on the [Starlette](https://www.starlette.io/) ASGI framework and works well with the [Responder](https://responder.readthedocs.io/en/latest/).

This library provides event subscription interface,
just like Flask based [Slack Events API adapter](https://github.com/slackapi/python-slack-events-api),
it would be easy to switch from it.

Oh, one more point, this library can handle both sync and async function for event callback :)

## Installation

```sh
TBD
```

## Setup Slack App with Event Subscription

[Follow the official document](https://github.com/slackapi/python-slack-events-api/blob/master/README.rst#--development-workflow) :)

## Examples

### Hello world using responder

```python
import responder
from slackevent_responder import SlackEventApp

slack_events_app = SlackEventApp(
    path="/events", slack_signing_secret=SLACK_SIGNING_SECRET
)

@slack_events_app.on("reaction_added")
def reaction_added(event_data):
    event = event_data["event"]
    emoji = event["reaction"]
    print(emoji)

api = responder.API()
api.mount('/slack', slack_events_app)

api.run(port=3000)
```

More examples can be found [here](./example/).
