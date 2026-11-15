# COUGAR CFV235 Vision on Linux

An unofficial Linux dashboard for the [COUGAR CFV235 Vision](https://cougargaming.com/us/products/cases/cfv235-vision/) 1920 × 462 USB LCD. It renders CPU, GPU, memory and cooling readings as a PNG and sends an initial background followed by dashboard overlays over Linux hidraw. A preview can run without a connected display.

![Dashboard preview showing sample CPU, GPU, memory and cooling readings](docs/dashboard-preview.png)

*Software preview rendered with sample readings. The hardware status below describes what has been observed on a physical LCD.*

## Hardware status

The CFV235 Vision LCD has been running stably for weeks on the project owner's Linux system. The owner confirmed this from regular use in November 2026. The original October Ubuntu test notes also record a Linux-generated background appearing on the physical panel.

| Feature | Evidence |
| --- | --- |
| Physical Linux display operation | Weeks of stable operation on the owner's system, which uses an initial background and continuous RGBA overlay updates. |
| Display a Linux-generated background | Visually observed in the original Ubuntu test. |
| Local dashboard rendering | Verified offline with both sample data and unavailable sensors. |

The release carries over the transfer sequence from the running Linux service. The owner confirmed the deployed configuration with continuous refresh. Brightness changes across different levels and host suspend/resume have no separate verification results.

## Install

Use Linux with hidraw, Python 3.10 or later and a user account with read/write access to the LCD. From the root of a local checkout on Debian or Ubuntu:

```sh
sudo apt install python3-venv fonts-dejavu-core lm-sensors
python3 -m venv .venv
.venv/bin/python -m pip install .
```

On other distributions, install the equivalent Python and sensor packages. Pillow is installed by pip. Fonts and `lm-sensors` are optional. The dashboard can also read the first GPU reported by `nvidia-smi` when it is available.

## USB permissions

Run `.venv/bin/cougar-cfv235 --detect` to identify the matching `/dev/hidrawN` device. If a later send fails with a permissions error, users in a local desktop session on a systemd-based distribution can install the included udev rule:

```sh
sudo install -m 0644 docs/70-cougar-cfv235.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
```

Reconnect the LCD to apply the rule during a safe maintenance window. The rule uses `uaccess` to grant access to the active local seat. On headless systems, an administrator can use a dedicated local group and a device-specific udev rule. The application uses the device name as well as the USB ID because the ID alone may match other devices.

## Run

```sh
# Render sample data without an LCD
.venv/bin/cougar-cfv235 --demo --preview demo.png

# Render local sensor data without touching USB
.venv/bin/cougar-cfv235 --preview live-preview.png

# Run continuous dashboard updates until Ctrl+C
.venv/bin/cougar-cfv235 --send --seconds 0 --interval 2

# Refresh for 20 seconds after the initial background and overlay
.venv/bin/cougar-cfv235 --send --seconds 20 --interval 2 --brightness 70
```

Ensure Linux owns the USB device before sending. If the LCD is passed through to a VM, close its LCD application and release the USB device on the guest side first. Run one LCD controller at a time. Press Ctrl+C to stop. Sending changes the displayed background and sets the selected brightness (100 by default). The program does not restore the previous screen contents. The timed refresh window starts after the initial background and overlay. An in-flight USB transfer may run past the window.

## Known limitations

- The target is the CFV235 Vision USB panel with the observed controller ID and name. Other revisions, the standalone LCD kit and the Mesh Vision have no compatibility results here.
- Missing readings display as `--`. CPU and memory usage come from Linux `/proc`. CPU temperature uses supported `lm-sensors` labels for AMD and Intel. Pump speed and coolant temperature require compatible `kraken2` readings. GPU readings use the first NVIDIA GPU exposed by `nvidia-smi`.
- The dashboard sends one background at startup and uses overlays for subsequent updates. Video, animations, official themes, firmware operations and system service installation are outside its scope.
- The refresh interval is a pause between updates. Reading sensors, rendering and transferring images adds time, so this is not a 60 fps video output.
- The firmware behavior after closing the application, reconnecting USB or resuming the host still needs hardware confirmation.

Run offline tests with `.venv/bin/python -m unittest discover -s tests -v`. See [the hardware test procedure](docs/hardware-test.md) to record results for a specific release.

## License

Overdijk Glas & Bouw (OGB) licenses its original code and documentation under the [MIT License](LICENSE). The USB implementation is Python code from the project's Linux dashboard development, based on observed USB behavior. Pillow is installed separately under its own license. COUGAR and its product names identify the supported hardware. This is an independent project.
