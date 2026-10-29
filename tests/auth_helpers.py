"""Enroll a real local test account; API regression tests never bypass authentication."""

from eil.auth import COOKIE, AuthStore

PASSWORD = "Synthetic-test-password-2026"


def sign_in(client):
    store = AuthStore(client.app.state.runs.store.directory)
    if not store.configured():
        store.enroll(store.bootstrap(), "test-owner", PASSWORD)
    token, user = store.login("test-owner", PASSWORD)
    client.cookies.set(COOKIE, token)
    return user
