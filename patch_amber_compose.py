"""Patch amber-compiled compose.yaml to fix agent container permissions.

amber-helper needs root to create the Docker proxy socket at /var/run/docker.sock,
but the compiler only sets user: 0:0 on infrastructure services, not agent services.
This script adds user: "0:0" to every service that uses amber-helper.

See: https://github.com/RDI-Foundation/amber/issues/XXX

Usage:
    amber compile scenario.json5 --docker-compose amber-out
    python3 patch_amber_compose.py amber-out/compose.yaml
    docker compose -f amber-out/compose.yaml up
"""

import re
import sys


def patch(path: str) -> None:
    with open(path) as f:
        content = f.read()

    original = content

    # 1. Add user: "0:0" to every service that uses amber-helper as entrypoint
    #    but doesn't already have a user: directive.
    #    These are the agent services that need root to create the proxy socket.
    content = re.sub(
        r"(\n  (\S+):\n(?:(?!  \S).)*?)(    entrypoint:\n    - /amber/bin/amber-helper)",
        lambda m: (
            m.group(1) + "    user: \"0:0\"\n" + m.group(3)
            if "user:" not in m.group(1)
            else m.group(0)
        ),
        content,
        flags=re.DOTALL,
    )

    # 2. Silence amber-otelcol — its logs are noisy and obscure agent output.
    content = re.sub(
        r"(  amber-otelcol:\n    image: [^\n]+)",
        r"\1\n    logging:\n      driver: none",
        content,
    )

    if content == original:
        print(f"Nothing to patch in {path}")
        return

    with open(path, "w") as f:
        f.write(content)

    patched = len(re.findall(r'user: "0:0"', content))
    print(f"Patched {path}:")
    print(f"  Added user: \"0:0\" to {patched} service(s)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <compose.yaml>")
        sys.exit(1)
    patch(sys.argv[1])
