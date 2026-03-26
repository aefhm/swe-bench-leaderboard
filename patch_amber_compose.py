"""Patch amber-compiled compose.yaml — silence noisy otelcol logs.

Usage:
    python3 patch_amber_compose.py amber-out/compose.yaml
"""

import re
import sys


def patch(path: str) -> None:
    with open(path) as f:
        lines = f.readlines()

    otelcol_silenced = False
    for idx, line in enumerate(lines):
        if re.match(r"^  amber-otelcol:\s*$", line):
            block_end = idx + 1
            while block_end < len(lines) and (lines[block_end].strip() == "" or re.match(r"^    ", lines[block_end])):
                if "logging:" in lines[block_end]:
                    otelcol_silenced = True
                    break
                block_end += 1
            if not otelcol_silenced:
                for j in range(idx + 1, block_end):
                    if "image:" in lines[j]:
                        lines.insert(j + 1, "    logging:\n")
                        lines.insert(j + 2, "      driver: none\n")
                        otelcol_silenced = True
                        break
            break

    if not otelcol_silenced:
        print(f"Nothing to patch in {path}")
        return

    with open(path, "w") as f:
        f.writelines(lines)

    print(f"Patched {path}: silenced amber-otelcol logging")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <compose.yaml>")
        sys.exit(1)
    patch(sys.argv[1])
