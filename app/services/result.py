"""Tiny helpers so every service returns the same dict shape."""


def ok(**data):
    return {"success": True, **data}


def fail(code):
    return {"success": False, "error": code}
