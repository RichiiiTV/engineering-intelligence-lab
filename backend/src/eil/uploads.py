"""Bound API bodies before JSON validation or multipart file spooling."""

from fastapi.responses import JSONResponse

from .pdf_ingest import MAX_PDF_BYTES


class UploadBodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if not (
            scope["type"] == "http"
            and scope["method"] in {"POST", "PUT", "PATCH", "DELETE"}
            and scope["path"].startswith("/api/")
        ):
            return await self.app(scope, receive, send)
        upload = scope["path"].startswith("/api/cases/") and scope["path"].endswith("/sources")
        cap = MAX_PDF_BYTES + 65536 if upload else 128 * 1024
        headers = dict(scope.get("headers", []))
        try:
            advertised = int(headers.get(b"content-length", b"0"))
        except ValueError:
            advertised = cap + 1
        body = bytearray()
        if 0 <= advertised <= cap:
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                chunk = message.get("body", b"")
                if len(body) + len(chunk) > cap:
                    break
                body.extend(chunk)
                if not message.get("more_body", False):
                    replayed = False

                    async def replay():
                        nonlocal replayed
                        if not replayed:
                            replayed = True
                            return {"type": "http.request", "body": bytes(body), "more_body": False}
                        return await receive()

                    return await self.app(scope, replay, send)
        response = JSONResponse(
            status_code=413,
            content={
                "detail": "Upload request exceeds 10 MiB plus bounded multipart metadata"
                if upload
                else "API request exceeds 128 KiB"
            },
        )
        return await response(scope, receive, send)
