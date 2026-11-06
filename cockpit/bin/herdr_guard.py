# ponytail: no-op. Sessions started before the interception was removed still call this hook until they relaunch;
# delete it, send_gate.py and inbox_hook.py once none of them runs.
