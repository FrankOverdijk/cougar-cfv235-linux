"""Generate CFV235 background reports and talk to Linux hidraw."""

import json
import math
import os
import re
import select
import struct
import time
from pathlib import Path

WIDTH, HEIGHT = 1920, 462
REPORT, CHUNK = 1024, 1000
HID_ID = "0003:00001D6B:00000126"
HID_NAME = "COUGAR Inc. COUGAR USB Device"
MAX_PNG_BYTES = CHUNK * 65535


def get_device():
    matches = []
    for node in Path("/sys/class/hidraw").glob("hidraw*"):
        try:
            u = (node / "device/uevent").read_text()
        except OSError:
            continue
        fields = dict(line.split("=", 1) for line in u.splitlines() if "=" in line)
        if fields.get("HID_ID") == HID_ID and fields.get("HID_NAME") == HID_NAME:
            matches.append("/dev/" + node.name)
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one COUGAR hidraw device, found {len(matches)}. Check the USB connection and VM passthrough."
        )
    return matches[0]


def stamp():
    return int(time.time() * 1000)


def ctrl(verb, seq, when, payload=None):
    head = f"{verb} 1\r\nSeqNumber={seq}\r\nDate={when}\r\n"
    if payload is not None:
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode(
            "ascii"
        )
        head += f"ContentType=json\r\nContentLength={len(body)}\r\n"
    else:
        body = b""
    data = (head + "\r\n").encode("ascii") + body
    ln = (len(data) + 5).to_bytes(2, "big")
    chksum = (sum(ln) + sum(data)) & 255
    safe = data.replace(b"\x5b", b"\x5b\x02").replace(b"\x5a", b"\x5b\x01")
    frame = b"\x5a" + ln + safe + bytes([chksum]) + b"\x5a"
    if len(frame) > REPORT:
        raise ValueError("Control frame too large")
    return frame.ljust(REPORT, b"\0")


def chunks(png, when, kind):
    count = math.ceil(len(png) / CHUNK)
    frame_id = time.localtime(when / 1000).tm_sec
    for i in range(count):
        part = png[i * CHUNK : (i + 1) * CHUNK]
        body = (
            bytes([frame_id])
            + count.to_bytes(2, "big")
            + i.to_bytes(2, "big")
            + bytes([kind])
            + bytes(15)
            + part
        )
        frame = b"\x5c" + len(body).to_bytes(2, "big") + body
        if len(frame) > REPORT:
            raise ValueError("Data frame too large")
        yield frame.ljust(REPORT, b"\0")


def check_png(png):
    signature = b"\x89PNG\r\n\x1a\n"
    if (
        len(png) < 33
        or len(png) > MAX_PNG_BYTES
        or not png.startswith(signature)
        or png[12:16] != b"IHDR"
        or struct.unpack(">II", png[16:24]) != (WIDTH, HEIGHT)
    ):
        raise ValueError(
            "Frame must be a 1920×462 PNG within the USB transfer size limit"
        )


def send(fd, packet):
    n = os.write(fd, packet)
    if n != REPORT:
        raise OSError(f"Short HID write: {n}")


def ack(fd, expected, phase, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        ready, _, _ = select.select(
            [fd], [], [], max(0.01, deadline - time.monotonic())
        )
        if not ready:
            continue
        try:
            data = os.read(fd, REPORT)
        except BlockingIOError:
            continue
        if not data:
            raise OSError("The HID device closed the connection")
        seq = re.search(rb"AckNumber=(\d+)", data[:100])
        if (
            not data.startswith(b"\x5a")
            or b"1 200\r\n" not in data[:24]
            or not seq
            or int(seq.group(1)) != expected
        ):
            raise RuntimeError(f"{phase}: unexpected USB response: {data[:110]!r}")
        if phase.endswith(("start", "finish")) and b'"state":"success"' not in data:
            raise RuntimeError(f"{phase}: target did not report a successful transfer")
        return
    raise TimeoutError(f"{phase}: no USB acknowledgment after {timeout} seconds")


def state_payload(data):
    gpu = data["gpu"]
    return {
        "network": {"upload": 0, "download": 0},
        "memory": {"total": 0, "used": 0, "load": 0, "temperature": 0, "speed": 0},
        "cpu": {
            "load": data["cpu_usage"] or 0,
            "temperature": data["cpu_temp"] or 0,
            "speedAverage": 0,
            "power": 0,
            "voltage": 0,
            "usage": 0,
        },
        "gpu": {
            "load": gpu.get("load") or 0,
            "temperature": gpu.get("temp") or 0,
            "fan": 0,
            "speed": 0,
            "power": 0,
            "voltage": 0,
        },
        "disk": {
            "total": 0,
            "used": 0,
            "load": 0,
            "activity": 0,
            "temperature": 0,
            "readSpeed": 0,
            "writeSpeed": 0,
        },
        "fans": [],
        "motherboard": {"temperature": 0},
        "timestamp": stamp(),
    }


def transfer_background(fd, seq, when, png):
    kind = 2
    filename = "1920X462.png"
    check_png(png)
    send(
        fd,
        ctrl(
            "POST transport",
            seq,
            when,
            {"type": "media", "fileSize": len(png), "fileName": filename},
        ),
    )
    ack(fd, seq + 1, "image start")
    for packet in chunks(png, when, kind):
        send(fd, packet)
    ack(fd, 0, "image data")
    send(
        fd,
        ctrl(
            "POST transported", seq + 1, stamp(), {"md5": "todo", "fileName": filename}
        ),
    )
    ack(fd, seq + 2, "image finish")
    return seq + 2
