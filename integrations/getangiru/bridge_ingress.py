"""Temporary HMAC-only ingress gateway for the Getangiru integration pilot.

No UI, GET, admin or user-authenticated API endpoints are routed. Remove this
pilot tunnel once a private authenticated production transport is available.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import http.client
import time
from threading import Lock

ALLOWED={"/__getangiru/ping","/__getangiru/ingest"}
window_lock=Lock()
window_start=0.0
window_count=0

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        global window_start,window_count
        if self.path not in ALLOWED:
            self.send_error(404);return
        with window_lock:
            now=time.monotonic()
            if now-window_start>=60:
                window_start=now;window_count=0
            window_count+=1
            over=window_count>100
        if over:
            self.send_error(429);return
        raw_length=self.headers.get("Content-Length","")
        if not raw_length.isdecimal() or int(raw_length)>6200:
            self.send_error(413);return
        if self.headers.get("Content-Type","").split(";")[0]!="application/json":
            self.send_error(415);return
        body=self.rfile.read(int(raw_length))
        forward={k:self.headers.get(k,"") for k in (
            "X-Getangiru-Timestamp","X-Getangiru-Nonce","X-Getangiru-Signature",
        )}
        forward["Content-Type"]="application/json"
        try:
            c=http.client.HTTPConnection("127.0.0.1",3000,timeout=6)
            c.request("POST",self.path,body=body,headers=forward)
            r=c.getresponse()
            data=r.read(1024)
            self.send_response(r.status)
            self.send_header("Content-Type","application/json")
            self.send_header("Cache-Control","no-store")
            self.send_header("Content-Length",str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            c.close()
        except (TimeoutError, OSError):
            self.send_error(502)
    def do_GET(self):
        self.send_error(404)
    def do_HEAD(self):
        self.send_error(404)
    def do_OPTIONS(self):
        self.send_error(405)
    def log_message(self,fmt,*args):
        # Do not log query strings or headers; only status.
        pass

if __name__=="__main__":
    ThreadingHTTPServer(("127.0.0.1",3100),Handler).serve_forever()
