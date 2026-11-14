#!/usr/bin/env python3
"""School Library API simulator: a re-implementation for DEVASC lab 4.5.5.

The DEVASC VM runs Cisco's Flask/flask-restplus application from /opt/API-SIMULATOR,
which is not published. This file is an independent re-implementation of its
behaviour, written from the lab text and notes on the original application.
Only the Python standard library is required (Python 3.8+); PyYAML is
used for application/yaml replies when it is installed.

    python3 school_library_sim.py --host 127.0.0.1 --port 80

Add "127.0.0.1 library.demo.local" to /etc/hosts so that the lab URLs work unchanged.

  GET    /                          School Library web page (loads the books page by page)
  GET    /api/v1/docs               Swagger UI page ("School Library API")
  GET    /api/v1/swagger.json       Swagger 2.0 (OpenAPI) description of the API
  POST   /api/v1/loginViaBasic      HTTP Basic cisco / Cisco123!  -> {"token": "cisco|..."}
  POST   /api/v1/loginViaJSON       {"username": ..., "password": ...} -> {"token": ...}
  GET    /api/v1/books              includeISBN, sortBy, author, page; 10 books per page,
                                    pages start at 0, RFC 5988 Link header, rate limited
  POST   /api/v1/books              X-API-KEY; adds a book (an existing id is overwritten)
  GET    /api/v1/books/<id>         one book
  PUT    /api/v1/books/<id>         X-API-KEY; updates an existing book
  DELETE /api/v1/books/<id>         X-API-KEY; deletes a book

Books and tokens live in memory only, as in the original: a restart brings back the
four seed books and invalidates every token.
"""
import argparse
import base64
import binascii
import json
import re
import secrets
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
from xml.sax.saxutils import escape

try:
    import yaml  # python3-yaml; the original answers application/yaml with yaml.dump()
except ImportError:  # pragma: no cover
    yaml = None

USERS = {"cisco": "Cisco123!"}
SEED_BOOKS = (
    {"id": 0, "title": "IP Routing Fundamentals", "author": "Mark A. Sportack", "isbn": "978-1578700714"},
    {"id": 1, "title": "Python for Dummies", "author": "Stef Maruch Aahz Maruch", "isbn": "978-0471778646"},
    {"id": 2, "title": "Linux for Networkers", "author": "Cisco Systems Inc.", "isbn": "000-0000000123"},
    {"id": 3, "title": "NetAcad: 20 Years Of Online-Learning", "author": "Cisco Systems Inc.",
     "isbn": "000-0000001123"},
)
PAGE_SIZE = 10            # books per page of GET /books
RATE_WINDOW = 10          # seconds; fixed windows aligned to multiples of 10 s of Unix time
RATE_LIMIT = 5            # a call is refused when the window counter is already above 5 (6 pass)
LINK_BASE = "http://library.demo.local/api/v1/books"   # the original hard-codes this host
SORT_KEYS = ("id", "title", "author", "isbn")
MEDIA_TYPES = ("application/json", "application/xml", "application/yaml")
VALIDATION_FAILED = "Input payload validation failed"

state_lock = threading.Lock()
books = [dict(book) for book in SEED_BOOKS]   # insertion order is kept
tokens = set()
rate_windows = {}

# ------------------------------------------------------------------ serialisers
def to_json(data):
    # The DEVASC VM runs Flask in debug mode: JSON is indented by 4 spaces + newline.
    return json.dumps(data, indent=4) + "\n"

def _xml_node(tag, value):
    if isinstance(value, dict):
        inner = "".join(_xml_node(key, item) for key, item in value.items())
        return '<%s type="dict">%s</%s>' % (tag, inner, tag)
    if isinstance(value, list):
        inner = "".join(_xml_node("item", item) for item in value)
        return '<%s type="list">%s</%s>' % (tag, inner, tag)
    if value is None:
        return '<%s type="null"></%s>' % (tag, tag)
    if isinstance(value, bool):
        return '<%s type="bool">%s</%s>' % (tag, str(value).lower(), tag)
    if isinstance(value, int):
        return '<%s type="int">%d</%s>' % (tag, value, tag)
    if isinstance(value, float):
        return '<%s type="float">%r</%s>' % (tag, value, tag)
    text = escape(str(value), {'"': "&quot;", "'": "&apos;"})
    return '<%s type="str">%s</%s>' % (tag, text, tag)

def to_xml(data):
    # Same shape as dicttoxml.dicttoxml(data): a <root> element, list members are <item>.
    if isinstance(data, dict):
        body = "".join(_xml_node(key, item) for key, item in data.items())
    elif isinstance(data, list):
        body = "".join(_xml_node("item", item) for item in data)
    else:
        body = escape(str(data))
    return '<?xml version="1.0" encoding="UTF-8" ?><root>%s</root>' % body

def to_yaml(data):
    if yaml is not None:
        return yaml.safe_dump(data, default_flow_style=False)
    return json.dumps(data, indent=2) + "\n"   # JSON is valid YAML; used only without PyYAML

SERIALISERS = {"application/json": to_json, "application/xml": to_xml, "application/yaml": to_yaml}

def negotiate(accept):
    """Pick the reply format like werkzeug's MIMEAccept.best_match; JSON by default."""
    if not accept:
        return MEDIA_TYPES[0]
    entries = []
    for part in accept.split(","):
        fields = [field.strip() for field in part.split(";")]
        mediatype = fields[0].lower()
        if not mediatype:
            continue
        quality = 1.0
        for field in fields[1:]:
            if field.startswith("q="):
                try:
                    quality = float(field[2:])
                except ValueError:
                    quality = 0.0
        if mediatype in ("*/*", "*"):
            specificity = 0
        elif mediatype.endswith("/*"):
            specificity = 1
        else:
            specificity = 2
        entries.append((mediatype, quality, specificity))
    best, best_quality, best_specificity = None, -1.0, -1
    for offer in MEDIA_TYPES:
        wildcard = offer.split("/")[0] + "/*"
        for mediatype, quality, specificity in entries:
            if quality <= 0 or quality < best_quality:
                continue
            if quality > best_quality or specificity > best_specificity:
                if mediatype in ("*/*", "*", offer, wildcard):
                    best, best_quality, best_specificity = offer, quality, specificity
    return best or MEDIA_TYPES[0]

# ------------------------------------------------------------------- validation
class ArgumentError(Exception):
    def __init__(self, name, message):
        Exception.__init__(self, message)
        self.name = name
        self.message = message

def parse_boolean(value):
    """Like flask-restplus inputs.boolean: true/1, false/0/empty, anything else is an error."""
    if not value:
        return False
    lowered = str(value).lower()
    if lowered in ("true", "1"):
        return True
    if lowered in ("false", "0"):
        return False
    raise ValueError("Invalid literal for boolean(): %s" % lowered)

# (required properties, {property: (type, min length, max length)})
BOOK_MODEL = (("author", "title"),
              {"id": ("integer", None, None), "title": ("string", 1, 200), "author": ("string", 1, 200)})
CREDENTIALS_MODEL = (("password", "username"),
                     {"username": ("string", 1, 32), "password": ("string", 1, 200)})

def validate(payload, model):
    """Return {} or an "errors" dictionary shaped like the jsonschema messages of flask-restplus."""
    required, properties = model
    if not isinstance(payload, dict):
        return {"": "%r is not of type 'object'" % (payload,)}
    errors = {}
    for name in required:
        if name not in payload:
            errors[name] = "%r is a required property" % name
    for name, (kind, low, high) in properties.items():
        if name not in payload:
            continue
        value = payload[name]
        if kind == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
            errors[name] = "%r is not of type 'integer'" % (value,)
        elif kind == "string" and not isinstance(value, str):
            errors[name] = "%r is not of type 'string'" % (value,)
        elif kind == "string" and len(value) < low:
            errors[name] = "%r is too short" % (value,)
        elif kind == "string" and len(value) > high:
            errors[name] = "%r is too long" % (value,)
    return errors

def marshal_book(book):
    """What @marshal_with(Book) returns: only id, title and author; nothing found -> nulls."""
    if book is None:
        return {"id": None, "title": None, "author": None}
    return {"id": book.get("id"), "title": book.get("title"), "author": book.get("author")}

# --------------------------------------------------------------- static content
SWAGGER = {
    "swagger": "2.0",
    "basePath": "/api/v1",
    "info": {
        "title": "School Library API",
        "version": "1",
        "description": "API access to the School Library - build your own apps using this API.",
    },
    "produces": list(MEDIA_TYPES),
    "consumes": ["application/json"],
    "securityDefinitions": {"apikey": {"type": "apiKey", "in": "header", "name": "X-API-KEY"}},
    "tags": [{"name": "/api/v1", "description": "Default namespace"}],
    "paths": {
        "/loginViaBasic": {
            "post": {
                "tags": ["/api/v1"],
                "operationId": "post_login_via_basic",
                "responses": {"200": {"description": "Success", "headers": {
                    "Authorization: Basic": {"type": "string",
                                             "description": "BASE64 encoded username:password"}}}},
            },
        },
        "/loginViaJSON": {
            "post": {
                "tags": ["/api/v1"],
                "operationId": "post_login_via_json",
                "parameters": [{"name": "payload", "in": "body", "required": True,
                                "schema": {"$ref": "#/definitions/Credentials"}}],
                "responses": {"200": {"description": "Success"}},
            },
        },
        "/books": {
            "get": {
                "tags": ["/api/v1"],
                "operationId": "get_books",
                "parameters": [
                    {"name": "includeISBN", "in": "query", "type": "boolean",
                     "description": "Include in the results the ISBN numbers. Default=false"},
                    {"name": "sortBy", "in": "query", "type": "string", "enum": list(SORT_KEYS),
                     "description": "Sort results using the specified parameter. Default=id"},
                    {"name": "author", "in": "query", "type": "string",
                     "description": "Return only books by the given Author."},
                    {"name": "page", "in": "query", "type": "integer",
                     "description": "Replies are split into pages of 10 records. The RFC 5988 'Link' "
                                    "response header points to the next page; use this parameter "
                                    "to request a page. Pages are numbered from 0."},
                ],
                "responses": {"200": {"description": "Success"}},
            },
            "post": {
                "tags": ["/api/v1"],
                "operationId": "post_books",
                "security": [{"apikey": []}],
                "parameters": [{"name": "payload", "in": "body", "required": True,
                                "schema": {"$ref": "#/definitions/Book"}}],
                "responses": {"200": {"description": "Success", "schema": {"$ref": "#/definitions/Book"}}},
            },
        },
        "/books/{id}": {
            "get": {
                "tags": ["/api/v1"],
                "operationId": "get_book",
                "parameters": [{"name": "id", "in": "path", "required": True, "type": "integer"}],
                "responses": {"200": {"description": "Success", "schema": {"$ref": "#/definitions/Book"}}},
            },
            "put": {
                "tags": ["/api/v1"],
                "operationId": "put_book",
                "security": [{"apikey": []}],
                "parameters": [{"name": "id", "in": "path", "required": True, "type": "integer"},
                               {"name": "payload", "in": "body", "required": True,
                                "schema": {"$ref": "#/definitions/Book"}}],
                "responses": {"200": {"description": "Success", "schema": {"$ref": "#/definitions/Book"}}},
            },
            "delete": {
                "tags": ["/api/v1"],
                "operationId": "delete_book",
                "security": [{"apikey": []}],
                "parameters": [{"name": "id", "in": "path", "required": True, "type": "integer"}],
                "responses": {"200": {"description": "Success", "schema": {"$ref": "#/definitions/Book"}}},
            },
        },
    },
    "definitions": {
        "Book": {
            "type": "object",
            "required": ["author", "title"],
            "properties": {
                "id": {"type": "integer", "description": "Id"},
                "title": {"type": "string", "description": "Book title", "minLength": 1, "maxLength": 200},
                "author": {"type": "string", "description": "Author", "minLength": 1, "maxLength": 200},
            },
        },
        "Credentials": {
            "type": "object",
            "required": ["password", "username"],
            "properties": {
                "username": {"type": "string", "description": "Username", "minLength": 1, "maxLength": 32},
                "password": {"type": "string", "description": "Password", "minLength": 1, "maxLength": 200},
            },
        },
    },
}

DOCS_HTML = r"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>School Library API</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@3.52.5/swagger-ui.css">
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@3.52.5/swagger-ui-bundle.js"></script>
  <script>
    window.ui = SwaggerUIBundle({url: "/api/v1/swagger.json", dom_id: "#swagger-ui", docExpansion: "list"});
  </script>
</body>
</html>
"""

LANDING_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>School Library</title>
<style>
body{margin:0;font-family:Arial,Helvetica,sans-serif;background:#f2f2f2}
header{display:flex;justify-content:space-between;align-items:center;background:#017cad;color:#fff;padding:12px 20px}
header a{color:#fff;font-weight:bold}
nav{float:left;width:170px;padding:20px}
nav a{display:block;margin:8px 0;color:#017cad;cursor:pointer}
main{margin-left:210px;padding:20px}
table{border-collapse:collapse;background:#fff}
th,td{border:1px solid #ccc;padding:4px 10px;text-align:left}
th{background:#017cad;color:#fff}
.tab{display:none}
</style>
</head>
<body>
<header>
<div>Welcome to the <b>School Library</b></div>
<div>Are you a developer? We have APIs! Click <a href="/api/v1/docs" target="_blank">here</a> for API docs.</div>
</header>
<nav>
<a data-tab="books">Our Books</a>
<a data-tab="hours">Open Hours</a>
<a data-tab="contact">Contact</a>
</nav>
<main>
<section id="books" class="tab">
<h4>Here is a list of our books currently in the library.</h4>
<table><thead><tr><th>Book ID</th><th>Title</th><th>Author</th></tr></thead><tbody id="book-rows"></tbody></table>
</section>
<section id="hours" class="tab"><h4>We are open every day from 9:00AM to 5:00PM.</h4></section>
<section id="contact" class="tab">
<h4>The School Library is located at the School Center.</h4>
<h4>E-mail: info@library.demo.local. Documentation: <a href="/api/v1/docs" target="_blank">REST API</a></h4>
</section>
</main>
<script>
// The book list is read through the API page by page: follow rel="next" of the Link
// header and, on 429 Too Many Requests, wait Retry-After seconds before trying again.
var generation = 0;
function loadBooks(url, gen) {
  if (gen !== generation) { return; }
  fetch(url, {headers: {"Accept": "application/json"}}).then(function (r) {
    var rows = document.getElementById("book-rows");
    if (r.status === 429) {
      var wait = parseInt(r.headers.get("Retry-After") || "1", 10);
      var note = rows.insertRow();
      note.innerHTML = "<td colspan=\"3\">Loading in " + wait + " seconds ...</td>";
      setTimeout(function () { note.remove(); loadBooks(url, gen); }, wait * 1000);
      return;
    }
    var link = r.headers.get("Link");
    return r.json().then(function (page) {
      page.forEach(function (b) {
        var tr = rows.insertRow();
        [b.id, b.title, b.author].forEach(function (v) { tr.insertCell().textContent = v; });
      });
      var next = link && /<[^>]*[?&]page=(\d+)>;\s*rel="next"/.exec(link);
      if (next) { loadBooks("/api/v1/books?page=" + next[1], gen); }
    });
  });
}
function show(tab) {
  document.querySelectorAll(".tab").forEach(function (s) { s.style.display = "none"; });
  document.getElementById(tab).style.display = "block";
  if (tab === "books") {
    generation += 1;
    document.getElementById("book-rows").innerHTML = "";
    loadBooks("/api/v1/books", generation);
  }
}
document.querySelectorAll("nav a").forEach(function (a) {
  a.addEventListener("click", function () { show(a.dataset.tab); });
});
show("books");
</script>
</body>
</html>
"""

NOT_FOUND_HTML = ('<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">\n<title>404 Not Found</title>\n'
                  '<h1>Not Found</h1>\n<p>The requested URL was not found on the server. If you entered '
                  'the URL manually please check your spelling and try again.</p>\n')

PAGES = {
    "/": (LANDING_HTML, "text/html; charset=utf-8"),
    "/api/v1/docs": (DOCS_HTML, "text/html; charset=utf-8"),
    "/api/v1/swagger.json": (json.dumps(SWAGGER, indent=4) + "\n", "application/json"),
}
BOOK_PATH = re.compile(r"/api/v1/books/(\d+)")

# ----------------------------------------------------------------------- server
class LibraryHandler(BaseHTTPRequestHandler):
    server_version = "SchoolLibrarySim/1.0"

    # ---- plumbing
    def send_body(self, status, body, content_type, headers=None):
        raw = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")       # flask-cors default
        for name, value in (headers or {}).items():
            self.send_header(name, str(value))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(raw)

    def reply(self, status, data, headers=None):
        mediatype = negotiate(self.headers.get("Accept"))
        self.send_body(status, SERIALISERS[mediatype](data), mediatype, headers)

    def not_allowed(self, allowed):
        self.reply(405, {"message": "The method is not allowed for the requested URL."},
                   {"Allow": ", ".join(sorted(set(allowed) | {"OPTIONS"}))})

    def read_body(self):
        """Read the whole request body (Content-Length or chunked) so that no unread bytes are left
        on the socket when the connection is closed after the reply."""
        if "chunked" in (self.headers.get("Transfer-Encoding") or "").lower():
            data = b""
            while True:
                size = int(self.rfile.readline(65537).split(b";")[0].strip() or b"0", 16)
                if size == 0:
                    while self.rfile.readline(65537) not in (b"\r\n", b"\n", b""):
                        pass                           # optional trailer lines
                    return data
                data += self.rfile.read(size)
                self.rfile.readline(65537)             # CRLF after the chunk
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length) if length > 0 else b""

    def read_payload(self):
        """Return (ok, payload). The payload is None unless the body is sent as JSON (like Flask)."""
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json" and not (ctype.startswith("application/") and ctype.endswith("+json")):
            return True, None
        try:
            return True, json.loads(self.body.decode("utf-8"))
        except ValueError as exc:                  # JSONDecodeError and UnicodeDecodeError
            self.reply(400, {"message": "Failed to decode JSON object: %s" % exc})
            return False, None

    def api_key_error(self):
        key = self.headers.get("X-API-KEY")        # header names are case-insensitive
        if key is None:
            return 400, {"error": "API key required"}
        with state_lock:
            if key in tokens:
                return None
        return 401, {"error": "Invalid API key"}

    def take_rate_slot(self):
        """Global fixed-window limiter of GET /books. Returns the 429 headers when refused."""
        now = time.time()
        window = int(now // RATE_WINDOW) * RATE_WINDOW
        with state_lock:
            for old in [w for w in rate_windows if w < window]:
                del rate_windows[old]
            count = rate_windows.get(window, 0)
            if count > RATE_LIMIT:
                return {"Retry-After": window + RATE_WINDOW - int(now),
                        "X-RateLimit-Limit": RATE_LIMIT,
                        "X-RateLimit-BucketLifetime": RATE_WINDOW}
            rate_windows[window] = count + 1
        return None

    # ---- dispatch
    def do_GET(self):
        self.dispatch("GET")

    def do_HEAD(self):                              # Flask answers HEAD on every GET route
        self.dispatch("GET")

    def do_POST(self):
        self.dispatch("POST")

    def do_PUT(self):
        self.dispatch("PUT")

    def do_DELETE(self):
        self.dispatch("DELETE")

    def do_PATCH(self):
        self.dispatch("PATCH")

    def do_OPTIONS(self):                           # CORS preflight, answered like flask-cors
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT")
        requested = self.headers.get("Access-Control-Request-Headers")
        if requested:
            self.send_header("Access-Control-Allow-Headers", requested)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def dispatch(self, method):
        self.body = b""
        try:
            self.body = self.read_body()
            self.route(method)
        except Exception:  # noqa: BLE001 - one bad request must not stop the simulator
            self.log_error("unhandled error\n%s", traceback.format_exc())
            self.reply(500, {"message": "Internal Server Error"})

    def route(self, method):
        parts = urlsplit(self.path)
        path = parts.path
        query = parse_qs(parts.query, keep_blank_values=True)
        if path in PAGES:
            if method != "GET":
                return self.not_allowed(("GET", "HEAD"))
            body, content_type = PAGES[path]
            return self.send_body(200, body, content_type)
        if path == "/api/v1/loginViaBasic":
            return self.login_basic() if method == "POST" else self.not_allowed(("POST",))
        if path == "/api/v1/loginViaJSON":
            return self.login_json() if method == "POST" else self.not_allowed(("POST",))
        if path == "/api/v1/books":
            if method == "GET":
                return self.list_books(query)
            if method == "POST":
                return self.add_book()
            return self.not_allowed(("GET", "HEAD", "POST"))
        match = BOOK_PATH.fullmatch(path)
        if match:
            book_id = int(match.group(1))
            if method == "GET":
                return self.get_book(book_id)
            if method == "PUT":
                return self.put_book(book_id)
            if method == "DELETE":
                return self.delete_book(book_id)
            return self.not_allowed(("DELETE", "GET", "HEAD", "PUT"))
        self.send_body(404, NOT_FOUND_HTML, "text/html; charset=utf-8")

    # ---- authentication
    def login_basic(self):
        user = password = None
        header = self.headers.get("Authorization") or ""
        if header[:6].lower() == "basic ":
            try:
                user, _, password = base64.b64decode(header[6:].strip()).decode("utf-8").partition(":")
            except (binascii.Error, UnicodeDecodeError):
                user = password = None
        if user is None or USERS.get(user) != password:
            # flask-httpauth's reply; a browser reacts with its own "Sign in" dialog
            return self.send_body(401, "Unauthorized Access", "text/html; charset=utf-8",
                                  {"WWW-Authenticate": 'Basic realm="Authentication Required"'})
        self.reply(200, {"token": self.new_token(user)})

    def login_json(self):
        ok, payload = self.read_payload()
        if not ok:
            return
        errors = validate(payload, CREDENTIALS_MODEL)
        if errors:
            return self.reply(400, {"errors": errors, "message": VALIDATION_FAILED})
        if USERS.get(payload["username"]) != payload["password"]:
            return self.reply(401, {"error": "Incorrect username or password"})
        self.reply(200, {"token": self.new_token(payload["username"])})

    @staticmethod
    def new_token(user):
        token = user + "|" + secrets.token_urlsafe()   # cisco|<43 URL-safe characters>
        with state_lock:
            tokens.add(token)
        return token

    # ---- books
    @staticmethod
    def argument(query, name, convert, default=None):
        if name not in query:
            return default
        value = query[name][0]                         # the first value wins, like reqparse
        try:
            return convert(value)
        except ValueError as exc:
            raise ArgumentError(name, str(exc))

    def list_books(self, query):
        refused = self.take_rate_slot()                # counted before the arguments are checked
        if refused:
            return self.reply(429, {"error": "Too many requests."}, refused)
        try:
            page = self.argument(query, "page", int)
            include_isbn = self.argument(query, "includeISBN", parse_boolean)
            sort_by = self.argument(query, "sortBy", str, default="id")
            if sort_by not in SORT_KEYS:
                raise ArgumentError("sortBy", "The value '%s' is not a valid choice for 'sortBy'." % sort_by)
            author = self.argument(query, "author", str)
        except ArgumentError as exc:
            return self.reply(400, {"errors": {exc.name: exc.message}, "message": VALIDATION_FAILED})
        page = page or 0
        with state_lock:
            snapshot = [dict(book) for book in books]
        headers = {}
        if page < len(snapshot) // PAGE_SIZE:
            headers["Link"] = '<%s?page=%d>; rel="next"' % (LINK_BASE, page + 1)
        chunk = snapshot[page * PAGE_SIZE:page * PAGE_SIZE + PAGE_SIZE]   # paginate first ...
        try:
            chunk.sort(key=lambda book: book[sort_by])                     # ... then sort the page
        except (KeyError, TypeError):                  # e.g. sortBy=isbn and a book without isbn
            return self.reply(500, {"message": "Internal Server Error"})
        if author:
            chunk = [book for book in chunk if book.get("author") == author]   # exact match
        if not include_isbn:
            chunk = [marshal_book(book) for book in chunk]
        self.reply(200, chunk, headers)

    def add_book(self):
        ok, payload = self.read_payload()
        if not ok:
            return
        errors = validate(payload, BOOK_MODEL)         # the body is validated before the key
        if errors:
            return self.reply(400, {"errors": errors, "message": VALIDATION_FAILED})
        problem = self.api_key_error()
        if problem:
            return self.reply(*problem)
        if "id" not in payload:                        # the original fails here with a KeyError
            return self.reply(500, {"message": "Internal Server Error"})
        with state_lock:
            existing = next((book for book in books if book["id"] == payload["id"]), None)
            if existing is not None:
                existing.update(payload)               # silent overwrite, the reply is all nulls
                result = None
            else:
                books.append(payload)                  # extra keys such as "isbn" are stored
                result = payload
        self.reply(200, marshal_book(result))

    def get_book(self, book_id):
        with state_lock:
            found = next((dict(book) for book in books if book["id"] == book_id), None)
        if found is None:
            # The original returns ("Not found", 404) through @marshal_with(Book), so the fields
            # are read from the string "Not found": "title" becomes the str.title method.
            return self.reply(404, {"id": None, "title": str("Not found".title), "author": None})
        self.reply(200, marshal_book(found))

    def put_book(self, book_id):
        ok, payload = self.read_payload()
        if not ok:
            return
        errors = validate(payload, BOOK_MODEL)
        if errors:
            return self.reply(400, {"errors": errors, "message": VALIDATION_FAILED})
        problem = self.api_key_error()
        if problem:
            return self.reply(*problem)
        with state_lock:
            existing = next((book for book in books if book["id"] == book_id), None)
            if existing is not None:                   # PUT never creates a book
                existing.update(payload)
                existing["id"] = book_id
            result = dict(existing) if existing is not None else None
        self.reply(200, marshal_book(result))

    def delete_book(self, book_id):
        global books
        problem = self.api_key_error()
        if problem:
            return self.reply(*problem)
        with state_lock:
            existing = next((book for book in books if book["id"] == book_id), None)
            books = [book for book in books if book["id"] != book_id]
        self.reply(200, marshal_book(existing))

def main():
    parser = argparse.ArgumentParser(description="School Library API simulator "
                                                 "(re-implementation for DEVASC lab 4.5.5)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=80)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), LibraryHandler)
    print("School Library API simulator (re-implementation) on http://%s:%d/ (docs: /api/v1/docs)"
          % (args.host, args.port), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == "__main__":
    main()
