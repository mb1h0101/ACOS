# ACOS Classroom v0.2 — implementation handoff

## Purpose

ACOS is not a reward/punishment or generic Mac lock-screen product.

The classroom problem is: students should be able to work normally inside the
digital resources chosen for the current lesson, while the teacher must be able
to temporarily pull the whole class back to the teacher and then return every
Mac to the exact working context without sticky grey screens or stranded
overlays.

Core classroom loop:

1. Teacher sets the websites/apps needed for this lesson.
2. ACOS applies that policy to student Macs.
3. Students work autonomously inside that boundary.
4. When the teacher needs the class, one control shows "請看老師".
5. Pressing the same control again removes the teacher overlay and students
   continue from the existing browser/app/document state.
6. Ending the class performs a hard restore to FREE/NONE.

## UX rules

- Teacher Console is Traditional Chinese by default.
- Do not expose DEMO / EXERCISE / REWARD / FREE / ATTENTION as a wall of modes.
- REWARD is not part of the classroom UX.
- The normal classroom screen has two conceptual steps only:
  - set lesson resources;
  - one reversible teacher-attention control.
- Teacher Mac is protected from student commands by default.
- Local self-testing is an explicit advanced opt-in.
- "結束課堂／解除全部限制" must always recover students.

## State and recovery rules

- Policy enforcement and teacher attention are separate layers.
- Policy notices are non-blocking and automatically disappear when the student
  returns to an allowed resource.
- Teacher FOCUS_NOW owns the overlay until the teacher releases it.
- Any mode change tears down the previous overlay.
- Overlay hide performs a hard Tk window destroy rather than only withdraw.
- FREE + NONE is the guaranteed classroom release state.

## Classroom policy semantics

- If the website allow-list is non-empty, only those hosts are allowed.
- If it is empty, website filtering is off.
- If the app allow-list is non-empty, only those apps are allowed.
- If it is empty, app filtering is off.
- Site checks only inspect the browser that is actually frontmost; a blocked
  background tab must not trigger a warning.

## Teacher-device protection

An agent connecting from the same Mac as Teacher Console is marked
protected_from_classroom. It is excluded from classroom targets unless the
teacher explicitly enables local test mode. Turning local test mode off
immediately returns the protected device to FREE/NONE.

## On-device acceptance test

Do not deploy to 30–40 Macs until this passes on one Teacher Mac + one Student Mac.

1. Start both apps. Teacher Mac must stay usable even if StudentAgent is installed.
2. Configure one allowed website and apply.
3. Allowed site works.
4. A different site is rejected with a non-blocking notice.
5. Return to the allowed site: the notice disappears automatically.
6. Press "請全班看老師": student sees the focus screen.
7. Press "讓學生繼續操作": focus screen disappears immediately.
8. Browser tab, app and document state are still present.
9. Repeat focus/release at least 10 times. No grey/stale overlay may remain.
10. Press "結束課堂／解除全部限制": all ACOS restrictions disappear.
11. Enable local teacher test mode, confirm Teacher Mac can be targeted.
12. Disable local teacher test mode while focused: Teacher Mac must immediately recover.

Only after all 12 pass should a second student Mac be added, then the rest of
the lab.
