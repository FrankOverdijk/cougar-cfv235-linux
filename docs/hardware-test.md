# Physical LCD test procedure

Use a CFV235 Vision test machine or an agreed maintenance window. Sending frames changes the visible background and brightness. Record the project commit, Linux distribution, kernel, controller revision if known and whether the display was attached directly.

1. Run `cougar-cfv235 --detect` and record whether it locates a single device.
2. Run `cougar-cfv235 --send --seconds 5 --brightness 70`. Compare the visible layout with the saved preview. Check that the edges are intact.
3. Run `cougar-cfv235 --send --seconds 0 --interval 2 --brightness 70`. Watch the clock change at the next minute boundary. Press Ctrl+C and record whether the last image remains on the panel.
4. Repeat a short run at two distinct visible brightness levels. Confirm the change by observing the backlight and return it to the desired level.
5. If applicable, check what happens after disconnect/reconnect and suspend/resume. Record any USB acknowledgments alongside the corresponding visual results.
6. If sharing a photo, crop it to the LCD and remove identifying information and image metadata.

| Check | Result |
| --- | --- |
| Continuous Linux operation | The project owner reports weeks of stable use with the existing Linux service. |
| Device detected | |
| First frame visible and edges intact | |
| Clock changes across refreshes | |
| Brightness visibly changes | |
| Panel state after exit | |
| Reconnect and suspend/resume | |
