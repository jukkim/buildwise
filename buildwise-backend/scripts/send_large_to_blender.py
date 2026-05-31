"""Send large Python scripts to Blender MCP by writing to temp file first."""

import json
import os
import select
import socket
import sys
import time


def send_code(host, port, code, timeout=600):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect((host, port))
    msg = json.dumps({"type": "execute_code", "params": {"code": code}})
    payload = (msg + "\n").encode("utf-8")
    # Send in chunks to avoid buffer issues
    chunk_size = 4096
    for i in range(0, len(payload), chunk_size):
        s.sendall(payload[i : i + chunk_size])
        time.sleep(0.01)

    buf = b""
    deadline = time.time() + timeout
    while time.time() < deadline:
        ready = select.select([s], [], [], 2.0)
        if ready[0]:
            chunk = s.recv(65536)
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
    script_path = sys.argv[1] if len(sys.argv) > 1 else "scripts/bmesh_sagrada_v4.py"
    host = sys.argv[2] if len(sys.argv) > 2 else "localhost"
    port = int(sys.argv[3]) if len(sys.argv) > 3 else 9876

    with open(script_path, encoding="utf-8") as f:
        code = f.read()

    # Strategy: write script to temp file on Blender side, then exec it
    # This avoids buffer truncation issues with large code payloads
    abs_path = os.path.abspath(script_path).replace("\\", "/")

    # First try direct execution (works for most scripts)
    print(f"Sending {script_path} ({len(code)} bytes) to Blender at {host}:{port}...")

    # Use file-based execution: tell Blender to read and exec the file directly
    exec_code = f'exec(open(r"{abs_path}", encoding="utf-8").read())'

    t0 = time.time()
    result = send_code(host, port, exec_code, timeout=600)
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
