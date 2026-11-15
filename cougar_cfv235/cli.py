"""Render a local preview or run a bounded USB display session."""

import argparse
import errno
import os
import sys
import time
from pathlib import Path

from . import dashboard, device


def run_display(args, data, png):
    import fcntl

    node = device.get_device()
    try:
        fd = os.open(node, os.O_RDWR | os.O_NONBLOCK)
    except PermissionError as exc:
        raise PermissionError(
            f"Cannot open {node}. See the USB permissions section."
        ) from exc

    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError(
                "Another instance is already using this display."
            ) from exc
        device.send(fd, device.ctrl("POST conn", 0, device.stamp()))
        device.ack(fd, 1, "connection")
        device.send(
            fd, device.ctrl("POST power", 1, device.stamp(), {"event": "resume"})
        )
        device.ack(fd, 2, "resume")
        device.send(
            fd, device.ctrl("STATE all", 2, device.stamp(), device.state_payload(data))
        )
        device.ack(fd, 3, "initial sensor state")
        sequence = device.transfer_background(fd, 3, device.stamp(), png)
        device.send(
            fd,
            device.ctrl(
                "POST brightness", sequence, device.stamp(), {"value": args.brightness}
            ),
        )
        device.ack(fd, sequence + 1, "brightness")
        sequence += 1
        print("First frame acknowledged. Check the physical LCD.", flush=True)

        deadline = time.monotonic() + args.seconds
        while time.monotonic() < deadline:
            time.sleep(max(0, min(args.interval, deadline - time.monotonic())))
            if time.monotonic() >= deadline:
                break
            data = dashboard.measure(data["_counter"])
            if time.monotonic() >= deadline:
                break
            sequence = device.transfer_background(
                fd, sequence, device.stamp(), dashboard.dashboard_png(data)
            )
            print(f"Frame acknowledged at {data['sample_time']}", flush=True)
    finally:
        os.close(fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description="COUGAR CFV235 Vision Linux dashboard")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument(
        "--send", action="store_true", help="send the dashboard to the LCD"
    )
    modes.add_argument(
        "--detect", action="store_true", help="find the LCD without opening it"
    )
    modes.add_argument(
        "--demo", action="store_true", help="render a preview with sample data"
    )
    parser.add_argument(
        "--preview",
        type=Path,
        default=Path("cougar-preview.png"),
        help="local PNG output path",
    )
    parser.add_argument(
        "--seconds",
        type=int,
        default=20,
        help="refresh for 0–60 seconds after the first frame",
    )
    parser.add_argument(
        "--interval", type=float, default=2, help="wait 1–10 seconds between updates"
    )
    parser.add_argument(
        "--brightness",
        type=int,
        default=100,
        help="brightness from 0 to 100 during --send",
    )
    args = parser.parse_args(argv)
    if not (
        0 <= args.seconds <= 60
        and 1 <= args.interval <= 10
        and 0 <= args.brightness <= 100
    ):
        parser.error("expected --seconds 0–60, --interval 1–10, and --brightness 0–100")
    if (args.detect or args.send) and not sys.platform.startswith("linux"):
        parser.error("USB access requires Linux with hidraw")

    try:
        if args.detect:
            print(device.get_device())
            return 0
        if args.demo:
            data = dashboard.demo_data()
        else:
            counter = dashboard.cpu_counter()
            time.sleep(0.35)
            data = dashboard.measure(counter)
        png = dashboard.dashboard_png(data)
        args.preview.write_bytes(png)
        print(f"Preview saved to {args.preview}", flush=True)
        if args.send:
            try:
                run_display(args, data, png)
            except OSError as exc:
                if exc.errno in (errno.ENODEV, errno.EIO):
                    raise OSError(
                        "USB communication failed. Check the LCD connection."
                    ) from exc
                raise
        return 0
    except KeyboardInterrupt:
        print("Stopped.", file=sys.stderr)
        return 130
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
