"""Patch amber-compiled compose.yaml to bypass the Docker gateway proxy.

The amber-docker-gateway:v0.1 drops connections ("connection closed before
message completed"), causing `docker run` inside containers to fail with
exit 125. This script strips the proxy config and mounts the real
/var/run/docker.sock into agent services directly.

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

    # 1. Strip AMBER_DOCKER_MOUNT_PROXY_SPEC_B64 so amber-helper doesn't
    #    create a proxy socket that conflicts with the real one.
    content = re.sub(r"\n\s*- AMBER_DOCKER_MOUNT_PROXY_SPEC_B64=[^\n]+", "", content)

    # 2. Mount the host Docker socket directly into every service that
    #    uses amber-helper (they have amber-helper-bin volumes).
    content = re.sub(
        r"(- amber-helper-bin:/amber/bin:ro)",
        r"\1\n    - /var/run/docker.sock:/var/run/docker.sock",
        content,
    )

    # 3. Grant docker-socket access to non-root agent services.
    #    Docker Desktop (macOS) maps the socket as root:root 0660 regardless
    #    of host permissions.  Adding supplementary GID 0 lets the agent user
    #    connect without running as root.
    content = re.sub(
        r"(- /var/run/docker.sock:/var/run/docker.sock)",
        r"\1\n    group_add:\n    - root",
        content,
    )

    # 4. Silence amber-otelcol — its logs are noisy and obscure agent output.
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

    mounts = content.count("/var/run/docker.sock:/var/run/docker.sock")
    proxy_removed = "AMBER_DOCKER_MOUNT_PROXY_SPEC_B64" not in content
    print(f"Patched {path}:")
    print(f"  Docker socket mounted into {mounts} service(s)")
    print(f"  Proxy spec removed: {proxy_removed}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <compose.yaml>")
        sys.exit(1)
    patch(sys.argv[1])
