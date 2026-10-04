"""What proki asks jev (services/jev.py: openjev, or any service like it): an activity's category, the label of a
window (core/labeling.py), a task's size and group, whether a note is a to-do, whether
you're still there.

Only short texts are ever sent: an app name or a website domain (e.g. "github.com"), a
tracked app's window title (to label it), a task's title.
"""

from __future__ import annotations

import requests

from proki.core.events import Category
from proki.services.jev import Jev

CATEGORY_CRITERIA = {
    Category.DEEP.value: "Cognitively demanding work that creates value and is hard to replicate: coding, writing, design, research, analysis",
    Category.SHALLOW.value: "Logistical or communication work that is easy to replicate: email, chat, scheduling, admin",
    Category.DISTRACTION.value: "Entertainment, news or social media unrelated to work",
    Category.NEUTRAL.value: "System utilities or tools that are neither: settings, file manager, music player, terminal housekeeping",
}


def suggest_category(client: Jev, activity: str) -> tuple[Category, float] | None:
    """Best-guess category and its probability, or None if the call fails."""
    try:
        answer = client.ask(
            f"A person spends time on this computer activity: {activity}",
            {
                "category": {
                    "type": "choice",
                    "instructions": "How should this activity be classified for focus tracking?",
                    "criteria": CATEGORY_CRITERIA,
                }
            },
        )["category"]
        choice = answer["choice"]
        return Category(choice), float(answer.get("probabilities", {}).get(choice, 0))
    except (requests.RequestException, KeyError, ValueError):
        return None


SIZE_MINUTES = {"under_25": 15, "25_to_50": 40, "50_to_120": 85, "over_120": 150, "unclear": None}

TASK_QUESTIONS = {
    "kind": {
        "type": "choice",
        "instructions": "What kind of work is this task?",
        "criteria": {
            "deep": "Cognitively demanding: writing, coding, designing, studying, analysing",
            "shallow": "Logistics or communication: email, messages, scheduling, admin, errands",
        },
    },
    "size": {
        "type": "choice",
        "instructions": "How long will this task take one focused person?",
        "criteria": {
            "under_25": "Under 25 minutes",
            "25_to_50": "25 to 50 minutes",
            "50_to_120": "Between 50 minutes and 2 hours",
            "over_120": "More than 2 hours",
            "unclear": "Impossible to tell: the task is too vague or depends on context not given",
        },
    },
    "specific": {
        "type": "noul",
        "instructions": "Is the task specific enough that someone could estimate its size and know when it is done?",
        "criteria": {"true": "Concrete scope and a clear end point", "false": "Vague, open-ended, or needs context that is not given"},
    },
    "offline": {
        "type": "noul",
        "instructions": "Can this task be done well away from a computer (e.g. reading on paper, writing or solving by hand, thinking it through on a walk)?",
        "criteria": {"true": "Needs no computer", "false": "Needs a computer or phone"},
    },
}


def assess_task(client: Jev, task: str):
    """Kind, estimated minutes and specificity of a task, or None if the call fails."""
    from proki.legacy.core.backlog import Assessment

    try:
        a = client.ask(f'A person\'s task: "{task}"', TASK_QUESTIONS)
        return Assessment(
            kind=a["kind"]["choice"],
            minutes=SIZE_MINUTES.get(a["size"]["choice"]),
            specific=float(a["specific"]["noul"]),
            offline=float(a["offline"]["noul"]) if "offline" in a else None,
        )
    except (requests.RequestException, KeyError, ValueError, TypeError):
        return None


def suggest_group(client: Jev, task: str, groups: list[str]) -> str | None:
    """The name of the existing goal group this task belongs to, or None (a new goal, or failure)."""
    if not groups:
        return None
    criteria = {f"g{i}": f"Part of the goal \"{name}\"" for i, name in enumerate(groups)}
    criteria["new"] = "Belongs to none of these goals"
    try:
        a = client.ask(
            f'A person\'s new task: "{task}"',
            {"group": {"type": "choice", "instructions": "Which of the person's goals does this task belong to?",
                       "criteria": criteria}},
        )["group"]
        choice = a["choice"]
        return groups[int(choice[1:])] if choice.startswith("g") and a.get("confidence", 1) >= 0.5 else None
    except (requests.RequestException, KeyError, ValueError, TypeError, IndexError):
        return None


def classify_activity(client: Jev, text: str) -> list[tuple[str, float]] | None:
    """What the user typed they did while away → (activity key, probability), best first.

    'other' = none of the taxonomy's activities. None if the call fails.
    """
    from proki.legacy.core.routines import ACTIVITY_CATEGORY, ACTIVITY_LABEL, TAXONOMY

    criteria = {key: f"{TAXONOMY[ACTIVITY_CATEGORY[key]][0]}: {label}" for key, label in ACTIVITY_LABEL.items()}
    criteria["other"] = "None of these"
    try:
        a = client.ask(
            f'While away from the computer, a person did this: "{text}"',
            {"activity": {"type": "choice", "instructions": "Which activity was it?", "criteria": criteria}},
        )["activity"]
        probabilities = {k: float(p) for k, p in a.get("probabilities", {}).items() if k in criteria}
        probabilities.setdefault(a["choice"], float(a.get("confidence", 0)))
        return sorted(probabilities.items(), key=lambda kv: -kv[1])
    except (requests.RequestException, KeyError, ValueError, TypeError):
        return None


def is_todo(client: Jev, note: str) -> float | None:
    """How likely a note is something the person needs to do (vs. just an idea or fact to keep)."""
    try:
        a = client.ask(
            f'While reading email, chat, news or social media, a person noted: "{note}"',
            {"todo": {"type": "noul", "instructions": "Is this something the person needs to do?",
                      "criteria": {"true": "An action to take: reply, buy, fix, book, read later, follow up",
                                   "false": "An idea, a fact or something interesting to remember"}}},
        )["todo"]
        return float(a["noul"])
    except (requests.RequestException, KeyError, ValueError, TypeError):
        return None


DOING_CRITERIA = {
    "watching": "Watching a video or stream on the screen",
    "listening": "Listening to audio, a call or a meeting at the computer",
    "reading": "Reading or thinking in front of the screen",
    "away": "Away from the computer: a break, a meal, errands, another room",
}


def still_there(client: Jev, context: str) -> float | None:
    """How likely the person stayed at the computer (watching, listening, reading) during a
    stretch without input, from `context` (what was in focus, how long, when). None on failure."""
    try:
        a = client.ask(context, {"doing": {
            "type": "choice",
            "instructions": "During that time without input, what was the person most likely doing?",
            "criteria": DOING_CRITERIA,
        }})["doing"]
        return 1.0 - float(a.get("probabilities", {}).get("away", 1.0 if a["choice"] == "away" else 0.0))
    except (requests.RequestException, KeyError, ValueError, TypeError):
        return None


def suggest_label(client: Jev, text: str, labels: dict[str, str]) -> tuple[str, float] | None:
    """Which label (slug → "name: description") fits an app and window title, and
    openjev's probability; None on failure. Sends the title (core/labeling.py)."""
    try:
        a = client.ask(
            f"A person has this window in focus on their computer (app · title): {text}",
            {"label": {"type": "choice", "instructions": "What kind of app or page is this?",
                       "criteria": labels}},
        )["label"]
        choice = a["choice"]
        return choice, float(a.get("probabilities", {}).get(choice, a.get("confidence", 0)))
    except (requests.RequestException, KeyError, ValueError, TypeError):
        return None
