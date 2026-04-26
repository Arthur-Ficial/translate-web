#!/usr/bin/env python3
"""
Run every documented snippet against the real translate binary and a real
live `translate --serve` server, capturing the rendered command line plus
the actual stdout. Writes one .cmd / .out pair per entry to data/snippets/.

build.sh substitutes these into the page via placeholders -- nothing on
the rendered site is hand-typed.
"""

from __future__ import annotations

import json
import os
import shlex
import socket
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SNIPPETS = ROOT / "corpus" / "snippets.json"
DEST = ROOT / "data" / "snippets"
DEST.mkdir(parents=True, exist_ok=True)


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def write_pair(name: str, cmd: str, out: str) -> None:
    (DEST / f"{name}.cmd").write_text(cmd)
    (DEST / f"{name}.out").write_text(out.rstrip("\n") + "\n")


def shell_capture(shell_cmd: str) -> str:
    proc = subprocess.run(["/bin/bash", "-lc", shell_cmd],
                          capture_output=True, text=True)
    if proc.returncode != 0 and not proc.stdout:
        return f"# exit {proc.returncode}\n{proc.stderr}"
    return proc.stdout


def trim_json(body: str, kind: str, n: int) -> str:
    """Truncate big language-list responses to keep snippets compact."""
    if not n: return body
    try:
        obj = json.loads(body)
    except json.JSONDecodeError:
        return body
    if kind == "trim_array" and isinstance(obj, list):
        obj = obj[:n] + [{"_": f"... {len(obj) - n} more"}] if len(obj) > n else obj
    elif kind == "trim_languages" and isinstance(obj, dict):
        langs = obj.get("data", {}).get("languages")
        if isinstance(langs, list) and len(langs) > n:
            obj["data"]["languages"] = langs[:n] + [{"_": f"... {len(langs) - n} more"}]
    return json.dumps(obj, indent=2, ensure_ascii=False)


def render_curl_cmd(entry: dict[str, Any], port: int) -> str:
    method = entry.get("method", "GET")
    path = entry["path"]
    parts = ["curl"]
    if method == "GET":
        parts += ["-s", f"http://127.0.0.1:{port}{path}"]
        return " ".join(parts)
    parts += ["-s", "-X", method]
    if "json" in entry:
        body = json.dumps(entry["json"], ensure_ascii=False)
        parts += ['-H "Content-Type: application/json"', "-d", shlex.quote(body)]
    elif "form" in entry:
        for k, v in entry["form"]:
            parts += ["--data-urlencode", shlex.quote(f"{k}={v}")]
    parts += [f"http://127.0.0.1:{port}{path}"]
    return " ".join(parts)


def run_curl(entry: dict[str, Any], port: int) -> tuple[str, str, str]:
    """Returns (display_cmd, pretty_body, wire_response).

    wire_response is the literal HTTP/1.1 status line + headers + body so the
    page shows actual server traffic, not a paraphrase. We strip volatile
    headers (date, cf-ray-style stuff doesn't appear locally but date does)
    so the build is reproducible.
    """
    method = entry.get("method", "GET")
    path = entry["path"]
    url = f"http://127.0.0.1:{port}{path}"

    base_args = ["-s", "-X", method]
    if "json" in entry:
        base_args += ["-H", "Content-Type: application/json", "-d",
                      json.dumps(entry["json"], ensure_ascii=False)]
    elif "form" in entry:
        for k, v in entry["form"]:
            base_args += ["--data-urlencode", f"{k}={v}"]

    # Pretty body
    body_proc = subprocess.run(["curl", *base_args, url],
                               capture_output=True, text=True, timeout=20)
    body = body_proc.stdout
    for kind in ("trim_array", "trim_languages"):
        if kind in entry:
            body = trim_json(body, kind, int(entry[kind]))
            break
    try:
        body = json.dumps(json.loads(body), indent=2, ensure_ascii=False)
    except json.JSONDecodeError:
        pass

    # Wire response (-i adds status line + response headers; we drop the
    # Date header so the build is reproducible)
    wire_proc = subprocess.run(["curl", "-s", "-i", "-X", method,
                                *([a for a in base_args if a not in ("-s", "-X", method)]),
                                url],
                               capture_output=True, text=True, timeout=20)
    wire_lines: list[str] = []
    in_body = False
    for line in wire_proc.stdout.splitlines():
        if not in_body:
            if line.strip() == "":
                in_body = True
                wire_lines.append("")
                continue
            if line.lower().startswith("date:"):
                continue
            wire_lines.append(line)
        else:
            wire_lines.append(line)
    # Replace the body portion with the pretty-printed JSON we already have.
    head = []
    for line in wire_lines:
        if line == "":
            head.append("")
            break
        head.append(line)
    wire = "\n".join(head + [body])

    public_cmd = render_curl_cmd(entry, 8989).replace(f"127.0.0.1:{port}", "localhost:8989")
    return public_cmd, body, wire


def start_server(bin_path: Path, port: int) -> subprocess.Popen[bytes]:
    proc = subprocess.Popen(
        [str(bin_path), "--serve", "--port", str(port), "--quiet"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return proc
        except OSError:
            time.sleep(0.05)
    proc.terminate()
    raise RuntimeError(f"server didn't start on port {port}")


def main() -> int:
    bin_path = Path(os.environ.get("TRANSLATE", "translate"))
    if bin_path.name == bin_path.as_posix():
        # PATH-only invocation -- resolve via shutil
        import shutil
        resolved = shutil.which(str(bin_path))
        if not resolved:
            print(f"FATAL: translate binary not on PATH", file=sys.stderr)
            return 2
        bin_path = Path(resolved)

    manifest = json.loads(SNIPPETS.read_text())

    print(f"== CLI snippets ({len(manifest['cli'])}) ==")
    for entry in manifest["cli"]:
        out = shell_capture(entry["shell"])
        write_pair(f"cli-{entry['id']}", "$ " + entry["shell"], out)
        print(f"  {entry['id']:32s}  {len(out)} bytes")

    port = free_port()
    print(f"\n== server snippets on port {port} ({len(manifest['server'])}) ==")
    server = start_server(bin_path, port)
    try:
        for entry in manifest["server"]:
            cmd, body, wire = run_curl(entry, port)
            write_pair(f"server-{entry['id']}", cmd, body)
            (DEST / f"server-{entry['id']}.wire").write_text(wire.rstrip("\n") + "\n")
            print(f"  {entry['id']:32s}  body={len(body)}  wire={len(wire)}")
    finally:
        server.terminate()
        try:
            server.wait(timeout=3)
        except subprocess.TimeoutExpired:
            server.kill()

    print(f"\nwrote {len(list(DEST.glob('*.cmd')))} pairs to {DEST.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
