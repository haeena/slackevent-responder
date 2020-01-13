import hashlib
import hmac
import json


def create_signature(signing_secret, timestamp, data):
    req = f"v0:{timestamp}:{data}"
    request_signature = (
        "v0="
        + hmac.new(
            signing_secret.encode(), req.encode(), hashlib.sha256
        ).hexdigest()
    )
    return request_signature


def load_event_fixture(event, as_string=True):
    filename = f"tests/data/{event}.json"
    with open(filename) as json_data:
        event_data = json.load(json_data)
        if not as_string:
            return event_data
        else:
            return json.dumps(event_data)
