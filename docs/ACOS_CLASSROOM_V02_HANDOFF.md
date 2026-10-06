# ACOS Classroom v0.2 — implementation handoff

## Purpose

ACOS is a classroom orchestration tool for a real Mac lab. It is not a reward/
punishment system, not a student-screen surveillance product, and not a
traditional teacher-screen broadcast product.

The classroom loop is:

1. Teacher chooses the website rule for the lesson:
   - only allow the listed sites,
   - only block the listed sites,
   - or do not restrict websites.
2. Teacher independently chooses the same kind of rule for Apps.
3. Students work normally inside those rules.
4. When the teacher needs attention, one control shows 「請看老師」.
5. The same control changes to 「讓學生繼續操作」 and must restore the
   student's previous working context without a stale grey screen.
6. 「結束課堂／解除全部限制」 is the guaranteed classroom release.

## Current enforcement model

Website/App enforcement is intentionally soft and classroom-oriented.

The Student Agent checks the foreground app/browser about every 1.5 seconds.
If the current resource violates the teacher's rule, ACOS shows a non-blocking
policy notice. When the student returns to an allowed resource, that notice
must disappear automatically.

This behaviour is acceptable for the current classroom goal. Do not replace it
with MDM/Network Extension work unless a later requirement explicitly demands
packet-level hard blocking.

## Student Agent macOS identity

The Student Agent is packaged as:

`/Applications/ACOS Student Agent.app`

with stable bundle identifier:

`com.acos.studentagent`

The LaunchAgent runs the executable inside this app bundle. This replaces the
old bare `/usr/local/acos/acos-agent` identity and gives macOS permission UI a
stable, visible ACOS application identity.

## Permissions

- Screen Recording is NOT required in classroom v0.2.
- Student screen thumbnails are not part of the classroom UI.
- Teacher screen broadcast is not part of the classroom UI.
- Browser site rules use Apple Events to read the current Chrome/Safari tab.
  macOS may ask once for Automation permission when this is first used.
- Do not tell the teacher to enable a nonexistent ACOS entry in Screen
  Recording or Accessibility.

## Discovery

Default deployment uses automatic Teacher Console discovery:

`TEACHER_CONSOLE.txt = AUTO`

The agent tries Bonjour/mDNS and then UDP beacon. A fixed `host:port` remains
only as a fallback for a school LAN that blocks discovery. Normal DHCP address
changes must not require editing student Macs.

## Teacher UI

The normal Teacher Console contains:
- website rule + list;
- App rule + list;
- Apply to class;
- 「請全班看老師 / 讓學生繼續操作」;
- 「結束課堂／解除全部限制」;
- simple student online/state cards.

Do not restore DEMO / EXERCISE / REWARD / FREE / ATTENTION as a wall of modes.
Do not restore thumbnails or Broadcast to the classroom UI.

## On-device acceptance test

Do not deploy to 30–40 Macs until this passes on one Teacher Mac + one Student Mac.

1. Install the new StudentAgent.pkg.
2. Confirm `/Applications/ACOS Student Agent.app` exists.
3. Teacher Console is found automatically even if the teacher IP differs from a previous lesson.
4. Teacher Console shows the student online.
5. Configure website allow-list and verify an allowed site works.
6. Visit a non-allowed site; ACOS shows the policy notice.
7. Return to an allowed site; the notice disappears automatically.
8. Repeat with website block-list.
9. Repeat allow/block/off for Apps.
10. Press 「請全班看老師」 and then 「讓學生繼續操作」 at least 10 times.
11. No grey/stale overlay remains and the student's original app/document remains.
12. Press 「結束課堂／解除全部限制」 and verify ACOS restrictions disappear.
13. Teacher Mac stays protected unless explicit local test mode is enabled.

Only after these pass should a second student Mac be added, then the rest of the lab.
