from cockpit import team

# The fixtures name sessions agent-<role>, and a few still carry the old- prefix of a rename.
team.configure("agent-", ["old-"])
