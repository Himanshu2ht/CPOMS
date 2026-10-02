from datetime import datetime, timezone


def utcnow():
    """Naive UTC 'now' (what MySQL DATETIME columns store)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
