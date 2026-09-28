# Functional Test Report

Generated from `tests/functional_report.json` (run: `python tests/functional_test.py`).

Run timestamp: 2026-09-28T20:16:45

## Result: 30/30 passed

| test | result | detail |
|------|--------|--------|
| allowlist allows exact host | PASS |  |
| allowlist allows subdomain | PASS |  |
| allowlist blocks other host | PASS |  |
| blocklist blocks listed | PASS |  |
| blocklist allows unlisted | PASS |  |
| site off allows everything | PASS |  |
| app blocklist blocks Messages | PASS |  |
| app blocklist allows Safari | PASS |  |
| app allowlist blocks Terminal | PASS |  |
| validate accepts good msg | PASS |  |
| validate rejects wrong version | PASS |  |
| validate rejects non-dict | PASS |  |
| session id anonymous format | PASS |  |
| json export is list of events | PASS |  |
| csv has header | PASS |  |
| csv contains no name column | PASS |  |
| agent connects | PASS |  |
| agent applied EXERCISE | PASS |  |
| command latency recorded | PASS |  |
| blocked_navigation logged | PASS | count=1 |
| blocked_app logged | PASS | count=1 |
| allowed content not blocked | PASS | 1->1 |
| emergency returns to EXERCISE | PASS |  |
| emergency clears overlay | PASS |  |
| reward applied | PASS |  |
| reward auto-returns to EXERCISE | PASS | class_mode=EXERCISE |
| reward_start + reward_end logged | PASS |  |
| first boot not flagged as recovery | PASS |  |
| second boot detects crash recovery | PASS | prev=s-1e434fbd3eb84a0c |
| crash_recovery event reported | PASS |  |

## Scope
Covers policy semantics, protocol validation, live connect + command dispatch,
soft enforcement (blocked site/app → analytics), emergency focus, reward
auto-return, crash-recovery flag, and export shape/privacy. macOS-only OS
behaviour is verified on-device per `QA_CHECKLIST.md`, never faked here.
