# -*- coding: utf-8 -*-
"""Optional real-browser smoke test for the final UI (Edge + CDP).

This is a manual/CI helper, not a unit test: it launches Microsoft Edge headless,
clicks the real buttons and reads the real DOM.  Requires Edge installed.

Run:
    python tools/ui_smoke_test.py
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import requests
import websocket

EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
PORT = 9223
ROOT = Path(__file__).resolve().parents[1]


def main():
    if not EDGE.exists():
        raise SystemExit("Edge not found")
    profile = ROOT / "outputs" / "edge_smoke_profile"
    proc = subprocess.Popen([
        str(EDGE), "--headless=new", "--disable-gpu", "--no-first-run",
        f"--remote-debugging-port={PORT}", "--remote-allow-origins=*",
        f"--user-data-dir={profile}", "--window-size=1600,1200",
        "http://127.0.0.1:7860/",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        target = None
        for _ in range(40):
            try:
                pages = requests.get(f"http://127.0.0.1:{PORT}/json", timeout=1).json()
                target = next((p for p in pages if p.get("type") == "page"), None)
                if target:
                    break
            except Exception:
                pass
            time.sleep(0.5)
        if not target:
            raise RuntimeError("no CDP page target")
        ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=20)
        counter = [0]

        def js(expr):
            counter[0] += 1
            ws.send(json.dumps({"id": counter[0], "method": "Runtime.evaluate",
                                "params": {"expression": expr, "returnByValue": True}}))
            while True:
                msg = json.loads(ws.recv())
                if msg.get("id") == counter[0]:
                    return msg["result"]["result"].get("value")

        time.sleep(4)
        print("title:", js("document.title"))
        print("start enabled:", js("!document.getElementById('startBtn').disabled"))
        js("document.getElementById('startBtn').click()")
        time.sleep(4)
        print("after start: status=", js("document.getElementById('statusText').textContent"),
              "processed=", js("document.getElementById('stProcessed').textContent"),
              "pause_enabled=", js("!document.getElementById('pauseBtn').disabled"))
        js("document.getElementById('pauseBtn').click()")
        time.sleep(1)
        print("after pause:", js("document.getElementById('statusText').textContent"),
              "resume_enabled=", js("!document.getElementById('resumeBtn').disabled"))
        js("document.getElementById('resumeBtn').click()")
        time.sleep(3)
        print("after resume: processed=", js("document.getElementById('stProcessed').textContent"))
        js("document.getElementById('stopBtn').click()")
        time.sleep(1)
        print("after stop:", js("document.getElementById('statusText').textContent"))
        js("document.getElementById('resetBtn').click()")
        time.sleep(1)
        print("after reset: processed=", js("document.getElementById('stProcessed').textContent"),
              "status=", js("document.getElementById('batchStatus').textContent"))
        # switch tabs and read headings
        js("window.__activateTab('experiments')")
        time.sleep(1)
        print("experiments heading:", js("document.querySelector('#page-experiments h2').textContent"))
        js("window.__activateTab('logs')")
        time.sleep(1)
        print("logs heading:", js("document.querySelector('#page-logs h2').textContent"))
        ws.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    main()
