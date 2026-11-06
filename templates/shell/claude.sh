# bash or zsh: source this from your shell rc, with AGENT_SUITE set to the suite's folder.
# Runs claude through the suite launcher: the role pane's session name, the role's launch flags, saved flags on a
# bare resume. AGENT_SESSION tells the guards which session they run in.
claude() {
  if [ -n "${CLAUDE_CONFIG_DIR-}" ] || [ -z "${AGENT_SUITE-}" ]; then command claude "$@"; return; fi
  local launcher="$AGENT_SUITE/tools/team/launcher.py" item code
  local -a out
  out=()
  while IFS= read -r -d '' item; do out+=("$item"); done < <(CLAUDE_WRAPPER_PID=$$ python3 "$launcher" args "$@"; printf '\0')
  AGENT_SESSION="${out[@]:0:1}" CLAUDE_WRAPPER_PID=$$ command claude "${out[@]:1}"
  code=$?
  CLAUDE_WRAPPER_PID=$$ python3 "$launcher" forget
  return $code
}
