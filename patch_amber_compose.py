"""Patch amber-compiled compose.yaml to fix agent container permissions.

amber-helper needs root to create the Docker proxy socket at /var/run/docker.sock,
but the compiler sets a non-root user on agent services. This script overrides
user to "0:0" on every service that uses amber-helper.

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
        lines = f.readlines()

    patched_services = []
    i = 0
    while i < len(lines):
        # Detect a top-level service definition (2-space indent, ends with colon)
        m = re.match(r"^  (\S+):\s*$", lines[i])
        if not m:
            i += 1
            continue

        service_name = m.group(1)
        service_start = i
        i += 1

        # Collect all lines belonging to this service (indented more than 2 spaces)
        has_amber_helper = False
        user_line_idx = None
        while i < len(lines) and (lines[i].strip() == "" or re.match(r"^    ", lines[i])):
            if "/amber/bin/amber-helper" in lines[i]:
                has_amber_helper = True
            if re.match(r'^    user:\s', lines[i]):
                user_line_idx = i
            i += 1

        if not has_amber_helper:
            continue

        if user_line_idx is not None:
            # Replace existing user line
            old_user = lines[user_line_idx].strip()
            if old_user == 'user: "0:0"' or old_user == "user: 0:0":
                continue  # already root
            lines[user_line_idx] = '    user: "0:0"\n'
            patched_services.append(service_name)
        else:
            # Insert user line right after the service name
            lines.insert(service_start + 1, '    user: "0:0"\n')
            patched_services.append(service_name)
            i += 1  # account for inserted line

    # Silence amber-otelcol
    otelcol_silenced = False
    for idx, line in enumerate(lines):
        if re.match(r"^  amber-otelcol:\s*$", line):
            # Check if logging is already set
            block_end = idx + 1
            while block_end < len(lines) and (lines[block_end].strip() == "" or re.match(r"^    ", lines[block_end])):
                if "logging:" in lines[block_end]:
                    otelcol_silenced = True
                    break
                block_end += 1
            if not otelcol_silenced:
                # Find the image line and insert after it
                for j in range(idx + 1, block_end):
                    if "image:" in lines[j]:
                        lines.insert(j + 1, "    logging:\n")
                        lines.insert(j + 2, "      driver: none\n")
                        otelcol_silenced = True
                        break
            break

    if not patched_services and not otelcol_silenced:
        print(f"Nothing to patch in {path}")
        return

    with open(path, "w") as f:
        f.writelines(lines)

    print(f"Patched {path}:")
    if patched_services:
        print(f"  Set user: \"0:0\" on {len(patched_services)} service(s): {', '.join(patched_services)}")
    if otelcol_silenced:
        print(f"  Silenced amber-otelcol logging")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <compose.yaml>")
        sys.exit(1)
    patch(sys.argv[1])
