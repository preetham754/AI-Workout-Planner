"""
Workout suggestor: collects your goals/equipment/level, filters a real
exercise database down to what actually fits, then asks a local LLM
(via Ollama) to turn that into a structured weekly plan.

The model only ever sees exercises we've already filtered as valid for
you, so it can't invent an exercise you can't do or suggest one that
needs equipment you don't have.

IMPORTANT: This is a general fitness tool, not medical advice. If you
have an injury, a medical condition, or haven't exercised in a while,
check with a doctor or physical therapist before starting a new
program. The model is instructed not to give specific advice around
injuries or pain -- it will tell you to consult a professional instead.

Prerequisites:
    ollama serve                 (or the Ollama app running)
    ollama pull llama3.2:3b      (or: ollama pull gemma2:2b)

Usage:
    python3 workout.py
    python3 workout.py --model gemma2:2b
"""

import argparse
import json
import sys

import requests

from retriever import WorkoutRetriever, GOAL_TO_CATEGORIES

OLLAMA_URL = "http://localhost:11434/api/generate"

SYSTEM_PROMPT = """You are a knowledgeable fitness assistant creating a workout plan.

Build the plan using ONLY the exercises listed in the context below.
Do not invent exercises, sets, or reps that aren't in the list --
use the default_scheme given for each exercise, adjusting slightly
only if needed to fit the session length.

User profile:
- Goal: {goal}
- Fitness level: {level}
- Days per week: {days}
- Session length: {session_length} minutes
- Equipment available: {equipment}
- Notes from user: {notes}

Safety rule: if the user's notes mention any pain, injury, or medical
condition, do NOT prescribe around it or give medical advice. Instead,
clearly recommend they consult a doctor or physical therapist before
starting, and keep the plan general.

Structure your response as:
1. A brief (1-2 sentence) summary of the plan's focus
2. A day-by-day breakdown (Day 1, Day 2, ...) using only the exercises below,
   with sets/reps for each
3. A short reminder to warm up before and stretch after each session

Available exercises:
{exercise_list}
"""


def format_exercise_list(exercises):
    if not exercises:
        return "(no matching exercises found for this equipment/level combination)"
    return "\n".join(
        f"- {e['name']} | {e['muscle_group']} | {e['category']} | {e['difficulty']} | {e['default_scheme']}"
        for e in exercises
    )


def collect_requirements():
    print("Let's build your workout plan. Answer a few quick questions.\n")

    print("Goal options: " + ", ".join(GOAL_TO_CATEGORIES.keys()))
    goal = input("Your goal: ").strip().lower()
    if goal not in GOAL_TO_CATEGORIES:
        print(f"  (not recognized, defaulting to 'general fitness')")
        goal = "general fitness"

    level = input("Fitness level (beginner/intermediate/advanced): ").strip().lower()
    if level not in ("beginner", "intermediate", "advanced"):
        level = "beginner"

    days = input("Days per week you can train (e.g. 3): ").strip()
    days = days if days else "3"

    session_length = input("Session length in minutes (e.g. 45): ").strip()
    session_length = session_length if session_length else "45"

    print("\nEquipment you have access to (comma-separated). Examples:")
    print("  bodyweight, dumbbells, barbell, bench, squat rack, resistance band,")
    print("  pull-up bar, kettlebell, jump rope, treadmill")
    equipment_raw = input("Equipment: ").strip()
    equipment = [e.strip().lower() for e in equipment_raw.split(",") if e.strip()]
    if not equipment:
        equipment = ["bodyweight"]

    notes = input("\nAnything else? (injuries, focus areas, preferences - optional): ").strip()
    if not notes:
        notes = "none"

    return {
        "goal": goal,
        "level": level,
        "days": days,
        "session_length": session_length,
        "equipment": equipment,
        "notes": notes,
    }


def ask_ollama(prompt, model):
    response = requests.post(
        OLLAMA_URL,
        json={"model": model, "prompt": prompt, "stream": True},
        stream=True,
    )
    response.raise_for_status()

    for line in response.iter_lines():
        if not line:
            continue
        chunk = json.loads(line)
        print(chunk.get("response", ""), end="", flush=True)
        if chunk.get("done"):
            break
    print()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="llama3.2:3b")
    parser.add_argument("--exercises", default="data/exercises.json")
    args = parser.parse_args()

    retriever = WorkoutRetriever(args.exercises)
    reqs = collect_requirements()

    matched = retriever.filter_exercises(
        goal=reqs["goal"],
        equipment=reqs["equipment"],
        level=reqs["level"],
    )

    print(f"\nFound {len(matched)} matching exercises for your equipment/level. Generating plan...\n")
    print("-" * 60)

    prompt = SYSTEM_PROMPT.format(
        goal=reqs["goal"],
        level=reqs["level"],
        days=reqs["days"],
        session_length=reqs["session_length"],
        equipment=", ".join(reqs["equipment"]),
        notes=reqs["notes"],
        exercise_list=format_exercise_list(matched),
    )

    try:
        ask_ollama(prompt, args.model)
    except requests.exceptions.ConnectionError:
        print("Couldn't reach Ollama. Is it running? Try: ollama serve")
        sys.exit(1)

    print("-" * 60)
    print("\nReminder: this is general fitness guidance, not medical advice.")
    print("Check with a doctor or physical therapist before starting a new program,")
    print("especially if you have an injury or health condition.")


if __name__ == "__main__":
    main()
