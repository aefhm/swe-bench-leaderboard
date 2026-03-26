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

import sys
import yaml


def patch(path: str) -> None:
    with open(path) as f:
        content = yaml.safe_load(f)

    patched_services = []

    services = content.get("services", {})
    for name, svc in services.items():
        entrypoint = svc.get("entrypoint", [])
        # Match services that use amber-helper as entrypoint
        # Override user even if already set — the compiler sets a non-root user
        # (e.g. 65532:65532) but amber-helper needs root to create the proxy socket.
        if "/amber/bin/amber-helper" in entrypoint and str(svc.get("user")) != "0:0":
            svc["user"] = "0:0"
            patched_services.append(name)

    # Silence amber-otelcol — its logs are noisy and obscure agent output.
    if "amber-otelcol" in services:
        services["amber-otelcol"].setdefault("logging", {})["driver"] = "none"

    if not patched_services:
        print(f"Nothing to patch in {path}")
        return

    with open(path, "w") as f:
        yaml.dump(content, f, default_flow_style=False, sort_keys=False)

    print(f"Patched {path}:")
    print(f"  Added user: \"0:0\" to {len(patched_services)} service(s): {', '.join(patched_services)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <compose.yaml>")
        sys.exit(1)
    patch(sys.argv[1])
