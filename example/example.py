import os

import uvicorn
from slack import WebClient as SlackClient
from starlette.applications import Starlette
from starlette.routing import Mount

from slackevent_responder import SlackEventApp


# Our app's Slack Event Adapter for receiving actions via the Events API
slack_signing_secret = os.environ["SLACK_SIGNING_SECRET"]
slack_events_app = SlackEventApp(
    path="/slack/events", slack_signing_secret=slack_signing_secret
)

# Create a SlackClient for your bot to use for Web API requests
slack_bot_token = os.environ["SLACK_BOT_TOKEN"]
slack_client = SlackClient(slack_bot_token)

app = Starlette(debug=True, routes=[Mount("/", slack_events_app)])


# Example responder to greetings
@slack_events_app.on("message")
def handle_message(event_data):
    message = event_data["event"]
    # If the incoming message contains "hi", then respond with a "Hello" message
    if message.get("subtype") is None and "hi" in message.get("text"):
        channel = message["channel"]
        message = "Hello <@%s>! :tada:" % message["user"]
        slack_client.chat_postMessage(channel=channel, text=message)


# Example reaction emoji echo
@slack_events_app.on("reaction_added")
def reaction_added(event_data):
    event = event_data["event"]
    emoji = event["reaction"]
    channel = event["item"]["channel"]
    text = ":%s:" % emoji
    slack_client.chat_postMessage(channel=channel, text=text)


# Error events
@slack_events_app.on("error")
def error_handler(err):
    print("ERROR: " + str(err))


# Once we have our event listeners configured, we can start the
# Flask server with the default `/events` endpoint on port 3000
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
