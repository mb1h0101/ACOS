# QA Checklist — Classroom v0.2

## A. Build / package
- ✅ TeacherConsole.app builds on macOS CI.
- ⬜ StudentAgent.pkg builds with `/Applications/ACOS Student Agent.app`.
- ⬜ App bundle ID is `com.acos.studentagent`.
- ⬜ LaunchAgent starts the executable inside the app bundle.

## B. Automatic discovery
- ⬜ Default `TEACHER_CONSOLE.txt` is `AUTO`.
- ⬜ Student finds Teacher Console via Bonjour/mDNS.
- ⬜ If mDNS fails, Student finds Teacher Console via UDP beacon.
- ⬜ Teacher DHCP/IP change does not require editing student Macs.
- ⬜ Fixed host:port still works as fallback.

## C. Classroom policy
- ✅ Website allow-list/block-list/off semantics exist in policy model.
- ✅ App allow-list/block-list/off semantics exist in policy model.
- ⬜ Allowed website works on a real Mac.
- ⬜ Disallowed website shows policy notice within the monitor interval.
- ⬜ Returning to allowed website automatically removes the notice.
- ⬜ Website block-list works.
- ⬜ App allow-list/block-list/off work.
- ⬜ Browser Automation prompt identifies ACOS Student Agent when required.

## D. Reversible teacher attention
- ⬜ 「請全班看老師」 shows the student focus overlay.
- ⬜ 「讓學生繼續操作」 removes it immediately.
- ⬜ Student's previous app/document/browser state remains.
- ⬜ Repeat 10 times with no stale grey/fullscreen overlay.
- ⬜ 「結束課堂／解除全部限制」 always restores normal operation.

## E. Teacher protection
- ⬜ Teacher Mac is protected by default even if Student Agent is installed.
- ⬜ Explicit local test mode can include the Teacher Mac.
- ⬜ Turning test mode off immediately releases the Teacher Mac.

## F. Permissions
- ✅ Screen Recording is not requested by classroom v0.2 installer.
- ✅ Student thumbnails are not in the classroom UI.
- ✅ Teacher Broadcast is not in the classroom UI.
- ⬜ Website rules function after required browser Automation approval.

## G. Rollout gate
Do not deploy to the full 30–40 Mac lab until all real-Mac checks above pass on
one Teacher Mac + one Student Mac, then on one Teacher Mac + two Student Macs.
