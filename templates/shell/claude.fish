# fish: copy to ~/.config/fish/functions/claude.fish, with AGENT_SUITE set to the suite's folder.
# Runs claude through the suite launcher: the role pane's session name, the role's launch flags, saved flags on a
# bare resume. AGENT_SESSION tells the guards which session they run in.
function claude
    if set -q CLAUDE_CONFIG_DIR; or not set -q AGENT_SUITE
        command claude $argv
        return
    end
    set -l launcher $AGENT_SUITE/tools/team/launcher.py
    set -l out (CLAUDE_WRAPPER_PID=$fish_pid python3 $launcher args $argv | string split0)
    AGENT_SESSION=$out[1] CLAUDE_WRAPPER_PID=$fish_pid command claude $out[2..-1]
    set -l code $status
    CLAUDE_WRAPPER_PID=$fish_pid python3 $launcher forget
    return $code
end
