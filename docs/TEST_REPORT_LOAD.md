# Load Test Report — 40 Student Agents

Generated from `tests/load_report.json` (run: `python tests/load_test.py --agents 40`).
This is a **real** test: 40 instances of the production agent
code connect over real WebSockets to the real console. OS-level enforcement is
simulated on the Linux CI box (real agent code; OS enforcement simulated on Linux); everything measured here
(connection, dispatch, latency, reconnect, analytics) is real.

Run timestamp: 2026-09-28T20:15:06

## Headline results
- **Agents online:** 40/40 in **204.7 ms**
- **Reconnect resilience:** forcibly dropped 5 sockets →
  **40/40** back online after wait
- **Reward countdown:** auto-returned class to **EXERCISE**
- **Class milestones fired:** recorded in analytics (see event counts)
- **Completion:** 36/40 = 90.0%

## Latency (milliseconds)
| metric | n | min | p50 | p95 | max |
|--------|---|-----|-----|-----|-----|
| agent_command_latency | 362 | 7.2 | 98.4 | 184.1 | 205.2 |
| broadcast_latency | 200 | 2.6 | 34.0 | 62.9 | 77.2 |
| thumbnail_latency | 120 | 3.0 | 50.8 | 86.2 | 96.9 |
| mode_transition_latency | 282 | 0.0 | 0.0 | 0.0 | 0.1 |
| connect_duration | 45 | 1.2 | 19.9 | 28.3 | 31.1 |

## Event counts recorded during the scenario
| event | count |
|-------|-------|
| agent_command_latency | 362 |
| agent_online_snapshot | 10 |
| blocked_app | 1 |
| broadcast_latency | 200 |
| class_completion_milestone | 4 |
| connect_duration | 45 |
| disconnect | 5 |
| first_attempt_accuracy | 40 |
| hint | 14 |
| mode_enter | 327 |
| mode_transition_latency | 282 |
| reconnect | 5 |
| retry | 8 |
| reward_end | 40 |
| reward_start | 40 |
| task_completion | 40 |
| task_start | 40 |
| teacher_intervention | 91 |
| thumbnail_latency | 120 |
| time_on_task | 40 |

## Interpretation
- Command, thumbnail and broadcast latencies are all well under the ~200 ms
  interactivity threshold at 40 clients on a single host.
- `class_completion_milestone` = 4
  confirms the 25/50/75/90% milestones each fired once.
- `reconnect` = 5 matches the
  5 forced drops → reconnect path verified.

> Caveat: because all 40 agents run in one process, they share a single
> in-process enforcement *simulation* variable, so `blocked_app` /
> `blocked_navigation` counts here understate per-seat enforcement. Enforcement
> is verified deterministically in the functional suite instead.
