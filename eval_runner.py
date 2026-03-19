"""Lightweight eval runner — sends an A2A eval request to the green agent and writes results.

Replaces agentbeats-client container with a simple Python script that runs on the host.
"""

import argparse
import json
import sys
import time
from uuid import uuid4

try:
    import httpx
except ImportError:
    print("Error: httpx required. Install with: pip install httpx")
    sys.exit(1)


def send_eval_request(
    endpoint: str,
    config: dict,
    timeout: int = 3600,
) -> dict:
    """Send an A2A message/send request and return the final task result."""
    message_payload = json.dumps({"participants": {}, "config": config})

    request = {
        "jsonrpc": "2.0",
        "method": "message/send",
        "id": uuid4().hex,
        "params": {
            "message": {
                "kind": "message",
                "role": "user",
                "messageId": uuid4().hex,
                "parts": [{"kind": "text", "text": message_payload}],
            }
        },
    }

    with httpx.Client(timeout=timeout) as client:
        response = client.post(endpoint, json=request)
        response.raise_for_status()
        data = response.json()

    result = data.get("result", data)

    # Extract text and data parts from the response
    output = {"status": "unknown", "text": "", "data": None}

    # Handle task response (has status + artifacts)
    if "status" in result:
        output["status"] = result["status"].get("state", "unknown")

    # Extract from artifacts
    for artifact in result.get("artifacts", []):
        for part in artifact.get("parts", []):
            if part.get("kind") == "text":
                output["text"] += part.get("text", "") + "\n"
            elif part.get("kind") == "data":
                output["data"] = part.get("data")

    # Fallback: extract from message parts
    if not output["data"] and "parts" in result:
        for part in result["parts"]:
            if part.get("kind") == "text":
                output["text"] += part.get("text", "") + "\n"
            elif part.get("kind") == "data":
                output["data"] = part.get("data")

    return output


def wait_for_agent(endpoint: str, timeout: int = 120):
    """Poll agent card endpoint until ready."""
    card_url = endpoint.rstrip("/") + "/.well-known/agent-card.json"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = httpx.get(card_url, timeout=3)
            if resp.status_code == 200:
                print(f"Agent ready at {endpoint}")
                return
        except Exception:
            pass
        time.sleep(2)
    print(f"Warning: agent at {endpoint} not responding after {timeout}s, proceeding anyway")


def main():
    parser = argparse.ArgumentParser(description="Send eval request to green agent")
    parser.add_argument("--endpoint", required=True, help="Green agent A2A endpoint URL")
    parser.add_argument("--instances", nargs="*", default=[], help="Instance IDs to evaluate")
    parser.add_argument("--max-instances", type=int, default=0, help="Max instances (0 = all)")
    parser.add_argument("--output", type=str, help="Path to write results JSON")
    parser.add_argument("--timeout", type=int, default=3600, help="Request timeout in seconds")
    parser.add_argument("--wait", action="store_true", help="Wait for agent to be ready first")
    args = parser.parse_args()

    if args.wait:
        wait_for_agent(args.endpoint)

    config = {}
    if args.instances:
        config["instances"] = args.instances
    if args.max_instances > 0:
        config["max_instances"] = args.max_instances

    print(f"Sending eval request to {args.endpoint}")
    print(f"Config: {json.dumps(config)}")

    try:
        result = send_eval_request(args.endpoint, config, timeout=args.timeout)
    except Exception as e:
        print(f"Error: {e}")
        error_result = {"error": str(e), "status": "failed"}
        if args.output:
            with open(args.output, "w") as f:
                json.dump(error_result, f, indent=2)
        sys.exit(1)

    print(f"Status: {result['status']}")
    if result["text"]:
        print(result["text"].strip())

    # Write output
    output_data = result["data"] if result["data"] else {"status": result["status"], "text": result["text"]}
    if args.output:
        with open(args.output, "w") as f:
            json.dump(output_data, f, indent=2)
        print(f"Results written to {args.output}")
    else:
        print(json.dumps(output_data, indent=2))

    # Exit non-zero if the task failed/was rejected
    if result["status"] in ("failed", "rejected"):
        sys.exit(1)


if __name__ == "__main__":
    main()
