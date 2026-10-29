# -*- coding: utf-8 -*-
"""Optional CDP check: upload the provided non-standard card and verify OOD UI."""

import base64
import json
import os
import subprocess
import time
from pathlib import Path

import requests
import websocket

EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
ROOT = Path(__file__).resolve().parents[1]
IMG = Path(os.environ.get("UI_IMAGE", ROOT / "outputs" / "user_cards" / "sanguosha_7S.jpg"))
OUT = Path(os.environ.get("UI_OUT", ROOT / "outputs" / "user_card_ood.png"))
PORT = 9225


def main():
    proc = subprocess.Popen([
        str(EDGE), "--headless=new", "--disable-gpu", "--no-first-run",
        f"--remote-debugging-port={PORT}", "--remote-allow-origins=*",
        f"--user-data-dir={ROOT / 'outputs' / 'edge_ood_profile'}",
        "--window-size=1720,1500", "http://127.0.0.1:7860/",
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
        ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=30)
        cid = [0]

        def cmd(method, params=None):
            cid[0] += 1
            ws.send(json.dumps({"id": cid[0], "method": method, "params": params or {}}))
            while True:
                msg = json.loads(ws.recv())
                if msg.get("id") == cid[0]:
                    return msg.get("result", {})

        def js(expr):
            return cmd("Runtime.evaluate", {"expression": expr, "returnByValue": True})["result"].get("value")

        time.sleep(4)
        doc = cmd("DOM.getDocument")
        node = cmd("DOM.querySelector", {"nodeId": doc["root"]["nodeId"], "selector": "#singleFile"})
        cmd("DOM.setFileInputFiles", {"nodeId": node["nodeId"], "files": [str(IMG)]})
        js("document.getElementById('singleFile').dispatchEvent(new Event('change',{bubbles:true}))")
        time.sleep(12)
        print("ood_box_visible:", js("!document.getElementById('oodBox').classList.contains('hidden')"))
        print("prediction:", str(js("document.getElementById('predCode').textContent")).encode("utf-8", "replace").decode("utf-8"))
        print("reason:", str(js("document.getElementById('oodReason').textContent")).encode("utf-8", "replace").decode("utf-8"))
        shot = cmd("Page.captureScreenshot", {"format": "png"})
        OUT.write_bytes(base64.b64decode(shot["data"]))
        print("screenshot:", OUT)
        ws.close()
    finally:
        proc.terminate()


if __name__ == "__main__":
    main()
