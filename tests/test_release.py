import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from cougar_cfv235 import cli, dashboard, device


class ReleaseTests(unittest.TestCase):
    def test_demo_cli_renders_png_without_opening_usb(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "demo.png"
            with patch.object(device, "get_device") as find_device:
                self.assertEqual(cli.main(["--demo", "--preview", str(output)]), 0)
                find_device.assert_not_called()
            with Image.open(output) as image:
                self.assertEqual(image.size, (1920, 462))
                self.assertEqual(image.format, "PNG")

    def test_background_reports_can_be_reassembled(self):
        png = dashboard.dashboard_png(dashboard.demo_data())
        device.check_png(png)
        packets = list(device.chunks(png, 0, 2))
        payloads = []
        for index, packet in enumerate(packets):
            self.assertEqual(len(packet), 1024)
            self.assertEqual(packet[0], 0x5C)
            self.assertEqual(packet[8], 2)
            self.assertEqual(int.from_bytes(packet[4:6], "big"), len(packets))
            self.assertEqual(int.from_bytes(packet[6:8], "big"), index)
            payload_size = int.from_bytes(packet[1:3], "big") - 21
            payloads.append(packet[24 : 24 + payload_size])
        self.assertEqual(b"".join(payloads), png)

    def test_control_report_escapes_bytes_and_keeps_pre_escape_length(self):
        report = device.ctrl("POST brightness", 0, 0, {"value": "[Z]"})
        self.assertEqual(len(report), 1024)
        self.assertEqual(report[0], 0x5A)
        self.assertIn(b'"value":"\x5b\x02\x5b\x01]"', report)
        self.assertEqual(report[int.from_bytes(report[1:3], "big") + 1], 0x5A)

    def test_incomplete_png_header_is_rejected(self):
        with self.assertRaises(ValueError):
            device.check_png(b"\x89PNG\r\n\x1a\n")

    def test_missing_sensors_render_as_a_valid_frame(self):
        with (
            patch.object(dashboard, "cpu_counter", return_value=None),
            patch.object(dashboard, "memory_data", return_value=(None, None, None)),
            patch.object(dashboard, "run", return_value=""),
        ):
            data = dashboard.measure()
        self.assertIsNone(data["cpu_temp"])
        with Image.open(io.BytesIO(dashboard.dashboard_png(data))) as image:
            self.assertEqual(image.size, (1920, 462))
