"""Cross-origin support for the unauthenticated public API.

The dashboard's CORS policy is deliberately narrow: it allows credentials, so it
can only name specific origins. The public endpoints under ``/api/v1/public``
have the opposite requirement — the embed snippet calls them from *every*
customer's website, and no origin list can enumerate those. They carry no
credentials and expose only data that is already public on the customer's own
page, so they are served with ``Access-Control-Allow-Origin: *``.

Without this, the snippet's fetch is blocked by the browser on every customer
domain in production and the install silently does nothing.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

PUBLIC_PATH_PREFIXES = ("/api/v1/public/",)

# Long enough that a preflight is not repeated for every page view.
PREFLIGHT_MAX_AGE = "86400"


def _is_public_path(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in PUBLIC_PATH_PREFIXES)


class PublicCorsMiddleware(BaseHTTPMiddleware):
    """Allow any origin to read the public preview API."""

    async def dispatch(self, request, call_next):
        if not _is_public_path(request.url.path):
            return await call_next(request)

        # Answer preflights here. The credentialed CORSMiddleware sitting closer
        # to the router would reject them for any origin outside its list.
        if request.method == "OPTIONS" and "access-control-request-method" in request.headers:
            return Response(
                status_code=204,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                    "Access-Control-Allow-Headers": request.headers.get(
                        "access-control-request-headers", "*"
                    ),
                    "Access-Control-Max-Age": PREFLIGHT_MAX_AGE,
                },
            )

        response = await call_next(request)

        # If the request came from an origin the dashboard policy already
        # allows, it has a credentialed origin-specific header. Leave it alone:
        # "*" and Allow-Credentials cannot legally be combined.
        if "access-control-allow-origin" not in response.headers:
            response.headers["Access-Control-Allow-Origin"] = "*"
            # The credentialed policy stamps this on any request carrying an
            # Origin, including ones it does not allow. Paired with "*" the
            # browser rejects the response outright, so drop it — these
            # endpoints never read credentials.
            if "access-control-allow-credentials" in response.headers:
                del response.headers["access-control-allow-credentials"]

        return response
