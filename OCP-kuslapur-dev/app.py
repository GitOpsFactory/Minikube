from http.server import BaseHTTPRequestHandler, HTTPServer
import json

class OrdersAPI(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path == "/healthz":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"healthy")
            return

        if self.path == "/orders":
            orders = [
                {"id": 101, "customer": "John", "status": "CREATED"},
                {"id": 102, "customer": "David", "status": "PROCESSING"},
                {"id": 103, "customer": "Sarah", "status": "COMPLETED"}
            ]

            data = json.dumps(orders).encode()

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        self.send_response(404)
        self.end_headers()

HTTPServer(("0.0.0.0", 8080), OrdersAPI).serve_forever()