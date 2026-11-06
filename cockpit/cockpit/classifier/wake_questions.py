from cockpit.classifier.jev_classifier import yes_no

# the first project's decision log, 2026-10-22 keep-warm rules: asked once per hour of an idle stretch, never per probe.
WAKE_QUESTIONS = {
    "wakes_within_hour": yes_no("Will `session` get new work or a message within the next hour?",
                                "A bead is in progress or waiting for it, other sessions depend on its answer, or the team is mid-task in working hours.",
                                "Nothing is waiting for it and nobody is expected to write to it soon."),
    "never_wakes": yes_no("Is `session` done for now, with nothing expected from it for many hours?",
                          "Its work is finished, it waits for an owner answer that has not come, or it is night with nothing queued.",
                          "More work is expected for it today."),
}
