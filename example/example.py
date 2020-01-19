import asyncio
import os

import uvicorn
from slack import WebClient as SlackClient
from starlette.applications import Starlette
from starlette.routing import Mount

from slackevent_responder import SlackEventApp


# Setup SlackEventApp to receive Events from Slack API
slack_signing_secret = os.environ["SLACK_SIGNING_SECRET"]
slack_events_app = SlackEventApp(
    slack_event_path="/events", slack_signing_secret=slack_signing_secret
)

# Mount SlackEventApp to Starlette
app = Starlette(debug=True, routes=[Mount("/slack", slack_events_app)])

# Create a SlackClient for your bot to use for Web API requests
slack_bot_token = os.environ["SLACK_BOT_TOKEN"]
slack_client = SlackClient(slack_bot_token)


# Example responder to greetings
@slack_events_app.on("message")
def handle_message(event_data):
    message = event_data["event"]
    # If the incoming message contains "hi", then respond with a "Hello" message
    if message.get("subtype") is None and "hi" in message.get("text"):
        channel = message["channel"]
        message = f"Hello <@{message['user']}>! :tada:"
        slack_client.chat_postMessage(channel=channel, text=message)


# Example reaction emoji echo
@slack_events_app.on("reaction_added")
def say_reaction_added(event_data):
    event = event_data["event"]
    emoji = event["reaction"]
    channel = event["item"]["channel"]
    text = f"reaction_added :{emoji}:"
    slack_client.chat_postMessage(channel=channel, text=text)


# Example reaction async delayed emoji echo
# multiple handler can subscribe a event
@slack_events_app.on("reaction_added")
async def say_twice_reaction_added(event_data):
    event = event_data["event"]
    emoji = event["reaction"]
    channel = event["item"]["channel"]
    text = (
        "I will say twice because it's important\n" f"reaction_added :{emoji}:"
    )
    await asyncio.sleep(5)
    slack_client.chat_postMessage(channel=channel, text=text)


# Error events
@slack_events_app.on("error")
def error_handler(err):
    print("ERROR: " + str(err))


# Once we have our event listeners configured, we can start the
# uvicorn server with `/skack/events` endpoint on port 8000
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
