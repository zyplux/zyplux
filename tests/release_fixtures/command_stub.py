from __future__ import annotations

import http.client
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit


def main() -> None:
    payload = {
        "program": Path(sys.argv[0]).name,
        "argv": sys.argv[1:],
        "cwd": str(Path.cwd()),
        "stdin": sys.stdin.read(),
    }
    endpoint = urlsplit(os.environ["AIRLOCK_TEST_ENDPOINT"])
    connection = http.client.HTTPConnection("127.0.0.1", endpoint.port)
    try:
        connection.request("POST", "/command", json.dumps(payload))
        reply = json.loads(connection.getresponse().read())
    finally:
        connection.close()
    stdout = reply["stdout"]
    sys.stdout.write(stdout + ("\n" if stdout and not stdout.endswith("\n") else ""))
    sys.stderr.write(reply["stderr"])
    sys.exit(reply["exit_code"])


if __name__ == "__main__":
    main()
