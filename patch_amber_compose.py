"""Patch amber-compiled compose.yaml to bypass the Docker gateway proxy.

The amber-docker-gateway:v0.1 drops connections ("connection closed before
message completed"), causing `docker run` inside containers to fail with
exit 125.  This script mounts /var/run/docker.sock at a non-default path
(/var/run/docker-host.sock) and sets DOCKER_HOST so agents use the real
socket instead of amber-helper's proxy.

We mount at /var/run/docker-host.sock (not /var/run/docker.sock) because
amber-helper tries to bind a proxy socket at /var/run/docker.sock based on
the mesh routing config.  Mounting the real socket at the same path causes
"failed to bind docker socket: Permission denied".

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

    # 2. Mount the host Docker socket at a non-default path into every
    #    service that uses amber-helper (they have amber-helper-bin volumes).
    #    Using /var/run/docker-host.sock avoids conflicting with the proxy
    #    socket that amber-helper binds at /var/run/docker.sock.
    content = re.sub(
        r"(- amber-helper-bin:/amber/bin:ro)",
        r"\1\n    - /var/run/docker.sock:/var/run/docker-host.sock",
        content,
    )

    # 3. Grant docker-socket access to non-root agent services.
    #    Docker Desktop (macOS) maps the socket as root:root 0660 regardless
    #    of host permissions.  Adding supplementary GID 0 lets the agent user
    #    connect without running as root.
    content = re.sub(
        r"(- /var/run/docker.sock:/var/run/docker-host\.sock)",
        r"\1\n    group_add:\n    - root",
        content,
    )

    # 4. Set DOCKER_HOST so the docker CLI and Python docker SDK use
    #    the real socket instead of amber-helper's proxy socket.
    content = re.sub(
        r"(- AMBER_TEMPLATE_SPEC_B64=[^\n]+)",
        r"\1\n    - DOCKER_HOST=unix:///var/run/docker-host.sock",
        content,
    )

    # 5. Silence amber-otelcol — its logs are noisy and obscure agent output.
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

    mounts = content.count("/var/run/docker-host.sock")
    docker_host_set = content.count("DOCKER_HOST=")
    proxy_removed = "AMBER_DOCKER_MOUNT_PROXY_SPEC_B64" not in content
    print(f"Patched {path}:")
    print(f"  Docker socket mounted into {mounts} service(s)")
    print(f"  DOCKER_HOST set in {docker_host_set} service(s)")
    print(f"  Proxy spec removed: {proxy_removed}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <compose.yaml>")
        sys.exit(1)
    patch(sys.argv[1])
