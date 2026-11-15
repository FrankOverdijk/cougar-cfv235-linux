# Physical LCD test procedure

Use a CFV235 Vision test machine or an agreed maintenance window. Sending frames changes the visible background and brightness. Record the project commit, Linux distribution, kernel, controller revision if known and whether the display was attached directly.

1. Run `cougar-cfv235 --detect` and record whether it locates a single device.
2. Run `cougar-cfv235 --send --seconds 0 --brightness 70`. Compare the visible layout with the saved preview. Check that the edges are intact.
3. Run `cougar-cfv235 --send --seconds 20 --interval 2 --brightness 70`. Watch the clock change on the physical panel. Record whether the last image remains after exit.
4. Repeat a single frame at two distinct visible brightness levels. Confirm the change by observing the backlight and return it to the desired level.
5. If applicable, check what happens after disconnect/reconnect and suspend/resume. Record any USB acknowledgments alongside the corresponding visual results.
6. If sharing a photo, crop it to the LCD and remove identifying information and image metadata.

| Check | Result |
| --- | --- |
| Device detected | |
| First frame visible and edges intact | |
| Clock changes across refreshes | |
| Brightness visibly changes | |
| Panel state after exit | |
| Reconnect and suspend/resume | |
