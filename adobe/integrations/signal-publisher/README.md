# LUCIDA signal publisher

This is a dependency-free Python client for the local Adobe signal bridge. It is a transport adapter, not an implementation of XIO, VIZZ or PUPILA.

The client accepts only the shared summary vocabulary and strips nested values and raw fields before making the HTTP request. The Adobe bridge remains the authoritative validator and redactor.

```python
from signal_publisher import SignalPublisher

publisher = SignalPublisher()
publisher.publish_event(
    "xio",
    "session-001",
    "radio.sample",
    metadata={
        "wifi_signal_percent": 84,
        "gateway_loss_percent": 1.5,
        "cell_rat": "nr",
    },
)
```

The same client can publish `vizz` attention summaries or `pupila` collaboration summaries. Proposals are optional, confirmation-only and never become host commands.

The default endpoint is `http://127.0.0.1:47921/signals`. Set `LUCIDA_ADOBE_URL` and `LUCIDA_ADOBE_TOKEN` when the local bridge uses another endpoint or bearer token.
