"""Send a Python script to Blender via MCP TCP (execute_code)."""

import json
import select
import socket
import sys
import time


def send_code(host, port, code, timeout=120):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect((host, port))
    msg = json.dumps({"type": "execute_code", "params": {"code": code}})
    s.sendall((msg + "\n").encode("utf-8"))

    buf = b""
    deadline = time.time() + timeout
    while time.time() < deadline:
        ready = select.select([s], [], [], 1.0)
        if ready[0]:
            chunk = s.recv(8192)
            if not chunk:
                break
            buf += chunk
            try:
                resp = json.loads(buf.decode("utf-8").strip())
                s.close()
                return resp
            except json.JSONDecodeError:
                continue
    s.close()
    if buf:
        return json.loads(buf.decode("utf-8").strip())
    raise TimeoutError("No response from Blender")


if __name__ == "__main__":
    script_path = sys.argv[1] if len(sys.argv) > 1 else "scripts/bmesh_hospital.py"
    host = sys.argv[2] if len(sys.argv) > 2 else "localhost"
    port = int(sys.argv[3]) if len(sys.argv) > 3 else 9876

    with open(script_path, encoding="utf-8") as f:
        code = f.read()

    print(f"Sending {script_path} to Blender at {host}:{port}...")
    t0 = time.time()
    result = send_code(host, port, code)
    dt = time.time() - t0
    print(f"Time: {dt:.1f}s")
    print(f"Status: {result.get('status', 'unknown')}")
    if result.get("result"):
        r = result["result"]
        if isinstance(r, dict):
            print(f"Result: {r.get('result', '')}")
        else:
            print(f"Result: {r}")
    if result.get("message"):
        print(f"Message: {result['message']}")
