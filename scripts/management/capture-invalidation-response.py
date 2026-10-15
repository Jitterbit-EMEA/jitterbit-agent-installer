#!/usr/bin/env python3
"""Bounded passive loopback response inspection; no raw bodies/headers exported."""

import argparse
import json
import re
import socket
import struct
import time
from datetime import datetime, timezone

ROUTE = b"PUT /axis/v1/token/3lo/invalidate "
KEYS = {
    "success",
    "status",
    "statusCode",
    "code",
    "error",
    "errorCode",
    "errorMessage",
    "errorMsg",
    "responseMessage",
    "reason",
    "details",
    "message",
    "result",
    "response",
    "data",
    "environmentId",
    "agentId",
    "requestId",
}
STATES = {"SUCCESS", "FAILED", "FAILURE", "ERROR", "OK", "true", "false"}


def safe_value(value, key=None, depth=0):
    if depth > 4:
        return "[DEPTH LIMIT]"
    if isinstance(value, dict):
        return {
            k: safe_value(v, k, depth + 1)
            for k, v in value.items()
            if isinstance(k, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", k)
        }
    if isinstance(value, list):
        return [safe_value(v, depth=depth + 1) for v in value[:10]]
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)) and key in {
        "statusCode",
        "code",
        "environmentId",
        "agentId",
    }:
        return value
    if (
        isinstance(value, str)
        and key
        and any(term in key.lower() for term in ["message", "msg", "reason", "detail", "error"])
        and key != "errorCode"
    ):
        terms = set(
            "cannot invoke because null pointer exception failed failure invalid invalidation token tokens environment agent organization project id not found missing does exist request response bad unavailable unauthorized forbidden access permission denied proxy connection connect refused timed timeout expired credentials cache manager service registration registered unable initialize initialized initialization map read write clear remove update delete synchronize authentication authorization error empty unsupported configured field key secret username password tls certificate ssl handshake protocol argument parameter state handler client factory".split()
        )
        return {
            "technicalTerms": [w for w in re.findall(r"[A-Za-z]+", value.lower()) if w in terms],
            "exceptionClasses": re.findall(
                r"\b[A-Za-z][A-Za-z0-9_.$]*(?:Exception|Error)\b", value
            ),
            "javaNullExpressions": re.findall(
                r'"((?:java\.[A-Za-z0-9_.$(), <>]+|this\.[A-Za-z0-9_.$]+|<local[0-9]+>))"', value
            ),
            "rawMessageWithheld": True,
        }
    if (
        isinstance(value, str)
        and key in {"status", "code", "errorCode"}
        and (value in STATES or re.fullmatch(r"[A-Z][A-Z_]{2,63}", value))
    ):
        return value
    return "[VALUE WITHHELD]"


def packet(frame):
    if len(frame) < 54 or frame[12:14] != b"\x08\x00":
        return None
    ip = frame[14:]
    ihl = (ip[0] & 15) * 4
    if ip[9] != 6 or ip[12:16] != b"\x7f\x00\x00\x01" or ip[16:20] != b"\x7f\x00\x00\x01":
        return None
    tcp = ip[ihl:]
    if len(tcp) < 20:
        return None
    offset = (tcp[12] >> 4) * 4
    src, dst, seq = struct.unpack("!HHI", tcp[:8])
    length = struct.unpack("!H", ip[2:4])[0]
    return src, dst, seq, tcp[offset : length - ihl]


def summarize(raw, request=False):
    head, sep, body = raw.partition(b"\r\n\r\n")
    if not sep:
        return None
    status = re.match(rb"HTTP/[0-9.]+ ([0-9]{3})", head)
    if not status and not (request and raw.startswith(ROUTE)):
        return None
    if status and int(status.group(1)) < 200:
        return summarize(body)
    headers = {}
    for line in head.split(b"\r\n")[1:]:
        key, colon, value = line.partition(b":")
        if colon:
            headers[key.strip().lower()] = value.strip()
    length = headers.get(b"content-length")
    chunked = b"chunked" in headers.get(b"transfer-encoding", b"").lower()
    if length and length.isdigit() and len(body) < int(length):
        return None
    if length and length.isdigit():
        body = body[: int(length)]
    if chunked:
        decoded = b""
        remaining = body
        try:
            while True:
                line, sep, remaining = remaining.partition(b"\r\n")
                if not sep:
                    return None
                size = int(line.split(b";")[0], 16)
                if size == 0:
                    break
                if len(remaining) < size + 2:
                    return None
                decoded += remaining[:size]
                remaining = remaining[size + 2 :]
            body = decoded
        except ValueError:
            return None
    elif not length:
        return None
    result = {
        "httpStatus": int(status.group(1)) if status else None,
        "bodyBytes": len(body),
        "chunked": chunked,
        "jsonBody": False,
        "safeResponse": None,
        "responseKeys": [],
    }
    try:
        data = json.loads(body)
        result.update({"jsonBody": True, "safeResponse": safe_value(data)})
        result["responseKeys"] = (
            list(result["safeResponse"]) if isinstance(result["safeResponse"], dict) else []
        )
    except (ValueError, UnicodeError):
        pass
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=int, default=120)
    args = parser.parse_args()
    if not 1 <= args.seconds <= 900:
        parser.error("seconds must be 1 to 900")
    flows = {}
    found = []
    deadline = time.monotonic() + args.seconds
    with socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(3)) as sock:
        sock.bind(("lo", 0))
        sock.settimeout(1)
        while time.monotonic() < deadline and not found:
            try:
                frame, addr = sock.recvfrom(65536)
            except TimeoutError:
                continue
            if addr[2] == socket.PACKET_OUTGOING:
                continue
            item = packet(frame)
            if item is None:
                continue
            src, dst, seq, payload = item
            if dst == 46912 and payload.startswith(ROUTE):
                flows[src] = {
                    "parts": {},
                    "requestParts": {seq: payload},
                    "observedAtUtc": datetime.now(timezone.utc).isoformat(),
                }
            elif dst == 46912 and src in flows and payload:
                flow = flows[src]
                flow["requestParts"][seq] = payload
                if sum(map(len, flow["requestParts"].values())) > 65536:
                    del flows[src]
                    continue
            elif src == 46912 and dst in flows and payload:
                flow = flows[dst]
                flow["parts"][seq] = payload
                if sum(map(len, flow["parts"].values())) > 65536:
                    del flows[dst]
                    continue
                raw = b"".join(flow["parts"][s] for s in sorted(flow["parts"]))
                result = summarize(raw)
                if result:
                    result["observedAtUtc"] = flow["observedAtUtc"]
                    reqraw = b"".join(flow["requestParts"][s] for s in sorted(flow["requestParts"]))
                    result["requestSummary"] = summarize(reqraw, request=True)
                    found.append(result)
    print(
        json.dumps(
            {
                "responses": found,
                "captureMatched": bool(found),
                "scope": "Only loopback PUT invalidation response; raw bytes retained only transiently in process memory; exported values allowlisted",
                "readOnly": True,
            }
        )
    )


if __name__ == "__main__":
    main()
