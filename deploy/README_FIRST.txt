ACOS classroom v0.2 — first run on a newly downloaded copy

IMPORTANT
A file downloaded from GitHub/browser can be tagged by macOS quarantine BEFORE
INSTALL.command is allowed to start. Therefore INSTALL.command cannot clear its
own quarantine until macOS lets it run.

On each Mac using a freshly downloaded/copy-with-quarantine ACOS_USB folder,
open Terminal and paste this ONE line:

xattr -dr com.apple.quarantine "$HOME/Downloads/ACOS_USB" && chmod +x "$HOME/Downloads/ACOS_USB"/*.command && bash "$HOME/Downloads/ACOS_USB/INSTALL.command"

After quarantine is cleared, the same ACOS_USB folder can be copied to a USB
stick and reused. If the copied folder no longer carries quarantine, future Macs
can double-click INSTALL.command directly.

Do not click "Move to Trash".
