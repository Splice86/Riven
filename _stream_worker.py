#!/usr/bin/env python3
"""Stream worker - runs as a subprocess to stream output to a file.

Do not run this directly. Use test_cli.py instead.
"""

import argparse
import json
import sys
import urllib.request
import urllib.error


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--message", required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--shard", default="default")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    output_file = open(args.output, "w", buffering=1)  # line-buffered

    payload = json.dumps({
        "message": args.message,
        "session_id": args.session,
        "shard_name": args.shard,
        "stream": True,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{args.api_url}/api/v1/messages",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
        method="POST",
    )

    # Accumulate thinking so we can flush it as one block
    thinking_buf = ""

    def flush_thinking():
        nonlocal thinking_buf
        if thinking_buf:
            output_file.write(f"\n--- thinking ---\n{thinking_buf.strip()}\n--------------------------\n")
            output_file.flush()
            thinking_buf = ""

    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            for line in resp:
                line = line.decode("utf-8", errors="replace")
                if not line.startswith("data: "):
                    continue
                data_str = line[6:].strip()
                if not data_str:
                    continue
                try:
                    event = json.loads(data_str)
                except json.JSONDecodeError:
                    output_file.write(f"[parse error] {data_str}\n")
                    output_file.flush()
                    continue

                # Buffer thinking content
                if "thinking" in event:
                    thinking_buf += event["thinking"]
                    continue

                # Non-thinking event arrived - flush thinking first, then handle
                flush_thinking()

                # Write token
                if "token" in event:
                    output_file.write(event["token"])
                    output_file.flush()

                # Write tool call
                elif "tool_call" in event:
                    tc = event["tool_call"]
                    output_file.write(
                        f"\n[call] {tc.get('name', '?')}({json.dumps(tc.get('arguments', {}))})"
                        f" [id={tc.get('id', '?')}]\n"
                    )
                    output_file.flush()

                # Write tool result
                elif "tool_result" in event:
                    tr = event["tool_result"]
                    if tr.get("error"):
                        output_file.write(
                            f"[result ERROR: {tr['error']}] {tr.get('content', '')}\n"
                        )
                    else:
                        output_file.write(f"[result] {tr.get('content', '')}\n")
                    output_file.flush()

                # Write error
                elif "error" in event:
                    output_file.write(f"\n[ERROR] {event['error']}\n")
                    output_file.flush()

                # Done - flush any remaining thinking
                elif "done" in event:
                    flush_thinking()
                    output_file.write("\n[done]\n")
                    output_file.flush()

    except urllib.error.HTTPError as e:
        output_file.write(f"\n[HTTP ERROR {e.code}] {e.reason}\n")
        output_file.flush()
        try:
            body = e.read().decode("utf-8", errors="replace")
            output_file.write(f"{body}\n")
        except Exception:
            pass
        output_file.flush()
        sys.exit(1)

    except urllib.error.URLError as e:
        output_file.write(f"\n[CONNECTION ERROR] {e.reason}\n")
        output_file.flush()
        sys.exit(1)

    finally:
        flush_thinking()
        output_file.close()


if __name__ == "__main__":
    main()
