from __future__ import annotations

import json
import os
import sqlite3
import html
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

PORT = int(os.environ.get("PORT", 8080))
BASE_DIR = os.path.dirname(__file__)
DB_PATH  = os.path.join(BASE_DIR, "messages.db")
HTML_FILE      = os.path.join(BASE_DIR, "proposal.html")
PROPOSAL_FILE  = os.path.join(BASE_DIR, "proposal.html")


# ── Database ────────────────────────────────────────────────────────────────

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                name      TEXT NOT NULL,
                email     TEXT NOT NULL,
                message   TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)


def save_message(name: str, email: str, message: str) -> None:
    with get_db() as conn:
        conn.execute(
            "INSERT INTO messages (name, email, message) VALUES (?, ?, ?)",
            (name, email, message),
        )


def get_all_messages() -> list[sqlite3.Row]:
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM messages ORDER BY created_at DESC"
        ).fetchall()


# ── Request handler ─────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):

    # ---- helpers ----

    def send_json(self, status: int, data: dict) -> None:
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, status: int, content: str) -> None:
        body = content.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_body(self) -> dict[str, str]:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode()
        parsed = parse_qs(raw)
        return {k: v[0] for k, v in parsed.items()}

    # ---- GET ----

    def do_GET(self):
        path = urlparse(self.path).path

        if path in ("/", "/index.html"):
            with open(HTML_FILE, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        elif path == "/proposal":
            with open(PROPOSAL_FILE, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        elif path == "/messages":
            rows = get_all_messages()
            self.send_html(200, render_messages_page(rows))

        elif path == "/api/messages":
            rows = get_all_messages()
            self.send_json(200, {
                "count": len(rows),
                "messages": [dict(r) for r in rows],
            })

        else:
            self.send_html(404, "<h1>404 Not Found</h1>")

    # ---- POST ----

    def do_POST(self):
        path = urlparse(self.path).path

        if path == "/contact":
            data = self.read_body()
            name    = data.get("name", "").strip()
            email   = data.get("email", "").strip()
            message = data.get("message", "").strip()

            if not (name and email and message):
                self.send_json(400, {"ok": False, "error": "All fields are required."})
                return

            save_message(name, email, message)
            self.send_json(200, {"ok": True, "message": "Message saved successfully."})

        else:
            self.send_html(404, "<h1>404 Not Found</h1>")

    def log_message(self, format, *args):
        print(f"[{self.address_string()}] {format % args}")


# ── Admin page renderer ──────────────────────────────────────────────────────

def render_messages_page(rows) -> str:
    rows_html = ""
    for r in rows:
        rows_html += f"""
        <tr>
          <td>{r['id']}</td>
          <td>{html.escape(r['name'])}</td>
          <td>{html.escape(r['email'])}</td>
          <td>{html.escape(r['message'])}</td>
          <td>{r['created_at']}</td>
        </tr>"""

    if not rows_html:
        rows_html = "<tr><td colspan='5' style='text-align:center;color:#888'>No messages yet.</td></tr>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>Messages — Admin</title>
  <style>
    body {{ font-family: Arial, sans-serif; background: #f0f4f8; color: #1a2e3b; margin: 0; padding: 32px; }}
    h1   {{ color: #0d6e63; margin-bottom: 20px; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff;
             border-radius: 8px; overflow: hidden;
             box-shadow: 0 4px 16px rgba(0,0,0,.08); }}
    th   {{ background: #0d6e63; color: #fff; padding: 12px 14px; text-align: left; font-size: .9rem; }}
    td   {{ padding: 12px 14px; border-bottom: 1px solid #dce5e8; font-size: .9rem; vertical-align: top; }}
    tr:last-child td {{ border-bottom: none; }}
    tr:hover td {{ background: #f7fbfb; }}
    a    {{ color: #0d6e63; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <h1>📬 Contact Messages</h1>
  <p><a href="/">&larr; Back to website</a> &nbsp;|&nbsp; {len(rows)} message(s) total</p>
  <table>
    <thead>
      <tr><th>#</th><th>Name</th><th>Email</th><th>Message</th><th>Received</th></tr>
    </thead>
    <tbody>{rows_html}</tbody>
  </table>
</body>
</html>"""


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Server running at http://localhost:{PORT}")
    print(f"Admin inbox  at http://localhost:{PORT}/messages")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
