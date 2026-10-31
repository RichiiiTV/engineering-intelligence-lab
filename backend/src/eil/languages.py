"""Bounded presentation preferences, frozen independently for each answer."""

from fastapi import HTTPException


def request_language(request):
    value = request.headers.get("x-eil-language", "de")
    if value not in {"de", "en"}:
        raise HTTPException(422, "Choose de or en")
    return value
