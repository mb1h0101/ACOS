"""
Canonical analytics event names.

Privacy rule enforced throughout ACOS: NO student names, usernames, emails,
device serials or any personally identifying value is ever recorded. The
only identifier is an anonymous per-boot Session ID (see protocol.new_session_id).

Every event carries: session_id, ts (epoch ms), and an optional `data` dict
of non-identifying fields.
"""

# Mode / lifecycle
MODE_ENTER = "mode_enter"                 # data: {mode}
MODE_TRANSITION_LATENCY = "mode_transition_latency"  # data: {from,to,ms}

# Task lifecycle (reported by learning content running inside the agent env)
TASK_START = "task_start"                 # data: {task_id}
TASK_END = "task_end"                     # data: {task_id}
TASK_COMPLETION = "task_completion"       # data: {task_id, completed:bool}
TIME_ON_TASK = "time_on_task"             # data: {task_id, ms}
FIRST_ATTEMPT_ACCURACY = "first_attempt_accuracy"  # data: {task_id, correct:bool}
RETRY = "retry"                           # data: {task_id, n}
HINT = "hint"                             # data: {task_id}
SKIP = "skip"                             # data: {task_id}
BACK = "back"                             # data: {task_id}

# Attention / enforcement
INACTIVE = "inactive"                     # data: {ms}
BLOCKED_NAVIGATION = "blocked_navigation" # data: {host}  (host only, never full URL query)
BLOCKED_APP = "blocked_app"               # data: {app}
TEACHER_INTERVENTION = "teacher_intervention"  # data: {kind}

# Connectivity
DISCONNECT = "disconnect"
RECONNECT = "reconnect"                    # data: {downtime_ms}
CRASH_RECOVERY = "crash_recovery"          # data: {prev_session_id}

# Reward
REWARD_START = "reward_start"             # data: {seconds}
REWARD_END = "reward_end"                 # data: {reason: 'timeout'|'teacher'}

# Class-level completion milestones (computed console-side, logged for the record)
CLASS_COMPLETION_MILESTONE = "class_completion_milestone"  # data: {pct}

# Latency / operations (measured console-side)
AGENT_COMMAND_LATENCY = "agent_command_latency"  # data: {ms, cmd}
BROADCAST_LATENCY = "broadcast_latency"          # data: {ms}
THUMBNAIL_LATENCY = "thumbnail_latency"          # data: {ms}
AGENT_ONLINE_SNAPSHOT = "agent_online_snapshot"  # data: {online, total, rate}

# Deployment timing (written by INSTALL.command / agent first-run)
INSTALL_DURATION = "install_duration"            # data: {ms}
PERMISSION_DURATION = "permission_duration"      # data: {ms, permission}
CONNECT_DURATION = "connect_duration"            # data: {ms}
