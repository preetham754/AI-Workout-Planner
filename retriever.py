"""
Structured retriever for workout suggestions.

Unlike free-text FAQ search, workout matching is naturally categorical
-- goal, available equipment, fitness level, target muscles -- so this
filters the exercise database with rules rather than keyword search.
This is still the RAG pattern: filter down to relevant, real exercises
first, then hand ONLY those to the LLM so it can't invent an exercise
or scheme that isn't actually in the database.
"""

import json

GOAL_TO_CATEGORIES = {
    "strength": ["strength"],
    "muscle gain": ["strength"],
    "weight loss": ["cardio", "strength", "core"],
    "cardio / endurance": ["cardio"],
    "flexibility / mobility": ["flexibility"],
    "general fitness": ["strength", "cardio", "core", "flexibility"],
}

LEVEL_RANK = {"beginner": 0, "intermediate": 1, "advanced": 2}


class WorkoutRetriever:
    def __init__(self, exercise_path):
        with open(exercise_path, "r") as f:
            self.exercises = json.load(f)

    def filter_exercises(self, goal, equipment, level, muscle_focus=None, max_results=25):
        """
        goal: key into GOAL_TO_CATEGORIES
        equipment: list of equipment strings the user has access to
                   (e.g. ["bodyweight", "dumbbells"])
        level: "beginner" | "intermediate" | "advanced"
        muscle_focus: optional list of muscle groups to prioritize
        """
        wanted_categories = GOAL_TO_CATEGORIES.get(goal, ["strength", "cardio", "core"])
        equipment_set = set(e.lower() for e in equipment)
        user_level_rank = LEVEL_RANK.get(level, 0)

        matches = []
        for ex in self.exercises:
            if ex["category"] not in wanted_categories:
                continue
            # every piece of equipment the exercise needs must be available
            if not set(ex["equipment"]).issubset(equipment_set):
                continue
            # don't suggest exercises harder than the user's level
            if LEVEL_RANK.get(ex["difficulty"], 0) > user_level_rank:
                continue
            matches.append(ex)

        if muscle_focus:
            focus_set = set(m.lower() for m in muscle_focus)
            prioritized = [e for e in matches if e["muscle_group"] in focus_set]
            rest = [e for e in matches if e["muscle_group"] not in focus_set]
            matches = prioritized + rest

        return matches[:max_results]


if __name__ == "__main__":
    r = WorkoutRetriever("data/exercises.json")
    results = r.filter_exercises(
        goal="strength",
        equipment=["bodyweight", "dumbbells", "bench"],
        level="beginner",
    )
    for ex in results:
        print(f"- {ex['name']} ({ex['muscle_group']}, {ex['difficulty']}) — {ex['default_scheme']}")
