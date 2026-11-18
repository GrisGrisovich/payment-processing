"""Local receiver for exercising real webhook delivery from Docker Compose."""

import os
from http.server import BaseHTTPRequestHandler, HTTPServer

statuses = iter(map(int, os.getenv("WEBHOOK_STATUSES", "200").split(",")))


class Receiver(BaseHTTPRequestHandler):
    status = 200

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        type(self).status = next(statuses, type(self).status)
        print(body.decode(), flush=True)
        self.send_response(self.status)
        self.end_headers()


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 9000), Receiver).serve_forever()
