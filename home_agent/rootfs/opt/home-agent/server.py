from http.server import BaseHTTPRequestHandler, HTTPServer

HOST = "0.0.0.0"
PORT = 8099

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Home Agent</title></head>
<body><h1>Home Agent is running</h1><p>Version 0.1.0</p></body>
</html>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        print(format % args)

HTTPServer((HOST, PORT), Handler).serve_forever()
