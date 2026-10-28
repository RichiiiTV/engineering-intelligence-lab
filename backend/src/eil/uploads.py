"""Bound multipart request bodies before Starlette spools uploaded files."""

from fastapi.responses import JSONResponse

from .pdf_ingest import MAX_PDF_BYTES


class UploadBodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if not (
            scope["type"] == "http"
            and scope["method"] == "POST"
            and scope["path"].startswith("/api/cases/")
            and scope["path"].endswith("/sources")
        ):
            return await self.app(scope, receive, send)
        cap = MAX_PDF_BYTES + 65536  # bounded multipart metadata overhead
        headers = dict(scope.get("headers", []))
        try:
            advertised = int(headers.get(b"content-length", b"0"))
        except ValueError:
            advertised = cap + 1
        body = bytearray()
        if advertised <= cap:
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
            content={"detail": "Upload request exceeds 10 MiB plus bounded multipart metadata"},
        )
        return await response(scope, receive, send)
