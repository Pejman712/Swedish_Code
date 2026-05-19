import random
import re
import asyncio
import os
import json
from pathlib import Path

import pdfplumber
import pandas as pd
import edge_tts
from playsound import playsound


# -----------------------------
# SETTINGS
# -----------------------------

PDF_PATH = "./data/swedish_verbs_table_v3.pdf"

SWEDISH_VOICE = "sv-SE-SofieNeural"
AUDIO_FILE = "swedish_word.mp3"

LEARNING_FILE = "swedish_learning_weights.json"

# Mastery scale:
# 0 = very weak, shown very often
# 5 = strong, shown less often
DEFAULT_MASTERY = 2
MIN_MASTERY = 0
MAX_MASTERY = 5

COLUMNS = [
    "English translation",
    "Presens",
    "Infinitiv",
    "Imperativ",
    "Past tense",
    "Present perfect tense"
]

SWEDISH_FORMS = [
    "Presens",
    "Infinitiv",
    "Imperativ",
    "Past tense",
    "Present perfect tense"
]


# -----------------------------
# PDF READING
# -----------------------------

def clean_cell(value):
    """
    Cleans text extracted from the PDF table.
    """
    if value is None:
        return ""

    value = str(value).strip()
    value = re.sub(r"\s+", " ", value)
    return value


def read_verbs_from_pdf(pdf_path):
    """
    Reads the Swedish verb table from the PDF.
    """
    all_rows = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()

            for table in tables:
                for row in table:
                    cleaned_row = [clean_cell(cell) for cell in row]

                    if not any(cleaned_row):
                        continue

                    row_text = " ".join(cleaned_row).lower()

                    if (
                        "english translation" in row_text
                        and "presens" in row_text
                        and "infinitiv" in row_text
                    ):
                        continue

                    if len(cleaned_row) >= 6:
                        cleaned_row = cleaned_row[:6]

                        if cleaned_row[0] and cleaned_row[1]:
                            all_rows.append(cleaned_row)

    df = pd.DataFrame(all_rows, columns=COLUMNS)
    df = df.drop_duplicates().reset_index(drop=True)

    return df


# -----------------------------
# LEARNING WEIGHTS
# -----------------------------

def make_learning_key(item, tense):
    """
    Creates a unique key for one English word + one tense/form.

    Example:
        eat | Presens | äter
    """
    english = item["English translation"]
    answer = item[tense]
    return f"{english} | {tense} | {answer}"


def load_learning_data():
    """
    Loads saved mastery data from JSON.
    """
    if not os.path.exists(LEARNING_FILE):
        return {}

    try:
        with open(LEARNING_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        if isinstance(data, dict):
            return data

        return {}

    except Exception:
        return {}


def save_learning_data(learning_data):
    """
    Saves mastery data to JSON.
    """
    with open(LEARNING_FILE, "w", encoding="utf-8") as file:
        json.dump(learning_data, file, ensure_ascii=False, indent=2)


def get_mastery(learning_data, key):
    """
    Gets mastery score for a word/form.
    """
    value = learning_data.get(key, DEFAULT_MASTERY)

    try:
        value = int(value)
    except ValueError:
        value = DEFAULT_MASTERY

    return max(MIN_MASTERY, min(MAX_MASTERY, value))


def set_mastery(learning_data, key, value):
    """
    Sets mastery score safely.
    """
    value = max(MIN_MASTERY, min(MAX_MASTERY, value))
    learning_data[key] = value


def increase_mastery(learning_data, key):
    """
    User knows the word better.
    Higher mastery means it appears less often.
    """
    current = get_mastery(learning_data, key)
    set_mastery(learning_data, key, current + 1)


def decrease_mastery(learning_data, key):
    """
    User needs more practice.
    Lower mastery means it appears more often.
    """
    current = get_mastery(learning_data, key)
    set_mastery(learning_data, key, current - 1)


def selection_weight_from_mastery(mastery):
    """
    Converts mastery into item selection weight.

    Lower mastery appears more often.

    Mastery 0 -> weight 6
    Mastery 1 -> weight 5
    Mastery 2 -> weight 4
    Mastery 3 -> weight 3
    Mastery 4 -> weight 2
    Mastery 5 -> weight 1
    """
    return (MAX_MASTERY + 1) - mastery


def show_learning_summary(learning_data):
    """
    Shows a small summary of saved mastery data.
    """
    if not learning_data:
        print("\nNo learning data saved yet.")
        return

    values = []

    for value in learning_data.values():
        try:
            values.append(int(value))
        except ValueError:
            pass

    if not values:
        print("\nNo valid learning data saved yet.")
        return

    weak = sum(1 for value in values if value <= 1)
    medium = sum(1 for value in values if 2 <= value <= 3)
    strong = sum(1 for value in values if value >= 4)

    print("\nLearning summary:")
    print("-----------------------------------")
    print(f"Weak items:    {weak}")
    print(f"Medium items:  {medium}")
    print(f"Strong items:  {strong}")
    print("-----------------------------------")


def reset_learning_data():
    """
    Deletes saved adaptive learning data.
    """
    if os.path.exists(LEARNING_FILE):
        os.remove(LEARNING_FILE)
        print(f"\nDeleted learning data: {LEARNING_FILE}")
    else:
        print("\nNo learning data file found.")


# -----------------------------
# TEXT-TO-SPEECH
# -----------------------------

async def create_swedish_audio(text, output_file=AUDIO_FILE):
    """
    Creates Swedish pronunciation audio.
    """
    communicate = edge_tts.Communicate(text, SWEDISH_VOICE)
    await communicate.save(output_file)


def pronounce_swedish(text):
    """
    Pronounces Swedish text aloud.
    """
    if not text or text == "-":
        return

    try:
        asyncio.run(create_swedish_audio(text, AUDIO_FILE))
        playsound(AUDIO_FILE)

        if os.path.exists(AUDIO_FILE):
            os.remove(AUDIO_FILE)

    except Exception as error:
        print(f"Could not pronounce: {text}")
        print(f"Error: {error}")


# -----------------------------
# ANSWER CHECKING
# -----------------------------

def normalize_answer(text):
    """
    Normalizes answers for comparison.
    Keeps Swedish letters but ignores case, extra spaces,
    and final exclamation marks.
    """
    if text is None:
        return ""

    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    text = text.rstrip("!")
    return text


def is_correct_answer(user_answer, correct_answer):
    """
    Allows multiple correct forms separated by '/'.

    Example:
        lade / la

    Accepted:
        lade
        la
    """
    user_answer = normalize_answer(user_answer)

    possible_answers = [
        normalize_answer(part)
        for part in correct_answer.split("/")
    ]

    return user_answer in possible_answers


# -----------------------------
# PRACTICE MODE HELPERS
# -----------------------------

def build_practice_items(df, learning_data):
    """
    Builds practice items for each verb.

    The weight for a whole verb is based on the weakest Swedish form.
    If any form is weak, the verb appears more often in practice mode.
    """
    practice_items = []

    records = df.to_dict(orient="records")

    for item in records:
        form_masteries = []

        for tense in SWEDISH_FORMS:
            value = item[tense]

            if not value or value == "-":
                continue

            key = make_learning_key(item, tense)
            mastery = get_mastery(learning_data, key)
            form_masteries.append(mastery)

        if not form_masteries:
            continue

        weakest_mastery = min(form_masteries)
        weight = selection_weight_from_mastery(weakest_mastery)

        practice_items.append({
            "item": item,
            "weakest_mastery": weakest_mastery,
            "weight": weight
        })

    return practice_items


def choose_weighted_practice_item(practice_items):
    """
    Chooses one practice item using adaptive weights.
    """
    weights = [entry["weight"] for entry in practice_items]
    return random.choices(practice_items, weights=weights, k=1)[0]


def mark_all_forms_known(item, learning_data):
    """
    Increases mastery for all Swedish forms of the current verb.
    """
    for tense in SWEDISH_FORMS:
        value = item[tense]

        if not value or value == "-":
            continue

        key = make_learning_key(item, tense)
        increase_mastery(learning_data, key)


def mark_all_forms_needs_practice(item, learning_data):
    """
    Decreases mastery for all Swedish forms of the current verb.
    """
    for tense in SWEDISH_FORMS:
        value = item[tense]

        if not value or value == "-":
            continue

        key = make_learning_key(item, tense)
        decrease_mastery(learning_data, key)


# -----------------------------
# PRACTICE MODE
# -----------------------------

def practice_mode(df):
    """
    Shows verbs with all Swedish forms using adaptive learning weights.

    Weak verbs appear more often.
    The user can mark a verb as known with k,
    or mark it for more practice with n.
    """
    if df.empty:
        print("No verbs found.")
        return

    learning_data = load_learning_data()
    show_learning_summary(learning_data)

    print("\nPractice mode")
    print("-----------------------------------")
    print("Commands:")
    print("Enter = next verb")
    print("1 = hear Presens")
    print("2 = hear Infinitiv")
    print("3 = hear Imperativ")
    print("4 = hear Past tense")
    print("5 = hear Present perfect tense")
    print("a = hear all forms")
    print("k = I know this verb, show it less often")
    print("n = I need more practice, show it more often")
    print("q = quit practice")
    print("-----------------------------------")

    while True:
        practice_items = build_practice_items(df, learning_data)

        if not practice_items:
            print("No valid practice items found.")
            return

        practice_entry = choose_weighted_practice_item(practice_items)
        item = practice_entry["item"]
        weakest_mastery = practice_entry["weakest_mastery"]

        while True:
            print("\n===================================")
            print(f"English: {item['English translation']}")
            print(f"Weakest mastery: {weakest_mastery}/{MAX_MASTERY}")
            print("-----------------------------------")
            print(f"1. Presens:                {item['Presens']}")
            print(f"2. Infinitiv:              {item['Infinitiv']}")
            print(f"3. Imperativ:              {item['Imperativ']}")
            print(f"4. Past tense:             {item['Past tense']}")
            print(f"5. Present perfect tense:  {item['Present perfect tense']}")

            command = input(
                "\nChoose pronunciation, Enter for next, k/n to adjust, or q: "
            ).strip().lower()

            if command == "q":
                save_learning_data(learning_data)
                print("Practice ended.")
                print(f"Learning data saved to: {LEARNING_FILE}")
                return

            if command == "":
                break

            if command in ["1", "2", "3", "4", "5"]:
                form_name = SWEDISH_FORMS[int(command) - 1]
                pronounce_swedish(item[form_name])
                continue

            if command == "a":
                for form_name in SWEDISH_FORMS:
                    value = item[form_name]
                    if value and value != "-":
                        print(f"{form_name}: {value}")
                        pronounce_swedish(value)
                continue

            if command == "k":
                mark_all_forms_known(item, learning_data)
                save_learning_data(learning_data)

                print("Marked this verb as known.")
                print("It will appear less often.")
                break

            if command == "n":
                mark_all_forms_needs_practice(item, learning_data)
                save_learning_data(learning_data)

                print("Marked this verb for more practice.")
                print("It will appear more often.")
                break

            print("Unknown command.")


# -----------------------------
# QUIZ MODE HELPERS
# -----------------------------

def build_quiz_items(df, selected_tenses, learning_data):
    """
    Builds all valid quiz items for selected tenses.
    """
    quiz_items = []

    records = df.to_dict(orient="records")

    for item in records:
        for tense in selected_tenses:
            correct_answer = item[tense]

            if not correct_answer or correct_answer == "-":
                continue

            key = make_learning_key(item, tense)
            mastery = get_mastery(learning_data, key)
            weight = selection_weight_from_mastery(mastery)

            quiz_items.append({
                "item": item,
                "tense": tense,
                "correct_answer": correct_answer,
                "key": key,
                "mastery": mastery,
                "weight": weight
            })

    return quiz_items


def choose_weighted_quiz_item(quiz_items):
    """
    Chooses one quiz item using adaptive weights.
    """
    weights = [entry["weight"] for entry in quiz_items]
    return random.choices(quiz_items, weights=weights, k=1)[0]


# -----------------------------
# QUIZ MODE
# -----------------------------

def choose_quiz_mode():
    """
    Lets the user choose what tense/form to practise.
    """
    print("\nChoose quiz mode:")
    print("1. Presens")
    print("2. Infinitiv")
    print("3. Imperativ")
    print("4. Past tense")
    print("5. Present perfect tense")
    print("6. Mixed")

    choice = input("\nEnter choice 1-6: ").strip()

    mapping = {
        "1": ["Presens"],
        "2": ["Infinitiv"],
        "3": ["Imperativ"],
        "4": ["Past tense"],
        "5": ["Present perfect tense"],
        "6": SWEDISH_FORMS
    }

    return mapping.get(choice, SWEDISH_FORMS)


def choose_number_of_questions():
    """
    Lets the user choose quiz length.
    Empty input means continuous mode until q.
    """
    value = input("\nNumber of questions, or Enter for endless quiz: ").strip()

    if value == "":
        return None

    try:
        number = int(value)
        if number <= 0:
            return None
        return number

    except ValueError:
        return None


def print_quiz_commands():
    """
    Prints available quiz commands.
    """
    print("\nQuiz commands:")
    print("q = quit")
    print("p = hear pronunciation again")
    print("s = skip")
    print("k = I know this word/form, show it less often")
    print("n = I need practice, show it more often")
    print()


def run_quiz(df):
    """
    Runs the Swedish verb quiz with adaptive learning weights.
    """
    if df.empty:
        print("No verbs found in the PDF.")
        return

    print(f"\nLoaded {len(df)} verbs from the PDF.")

    learning_data = load_learning_data()
    show_learning_summary(learning_data)

    selected_tenses = choose_quiz_mode()
    question_limit = choose_number_of_questions()

    print_quiz_commands()

    score = 0
    total = 0
    questions_seen = 0

    while True:
        quiz_items = build_quiz_items(df, selected_tenses, learning_data)

        if not quiz_items:
            print("No valid quiz items found for the selected mode.")
            return

        quiz_entry = choose_weighted_quiz_item(quiz_items)

        item = quiz_entry["item"]
        tense = quiz_entry["tense"]
        correct_answer = quiz_entry["correct_answer"]
        key = quiz_entry["key"]
        mastery = get_mastery(learning_data, key)

        english = item["English translation"]

        questions_seen += 1

        print("-----------------------------------")
        print(f"Question: {questions_seen}")
        print(f"English: {english}")
        print(f"Tense/form: {tense}")
        print(f"Current mastery: {mastery}/{MAX_MASTERY}")
        print("-----------------------------------")

        pronounce_swedish(correct_answer)

        while True:
            answer = input("Swedish: ").strip()
            command = answer.lower()

            if command == "q":
                save_learning_data(learning_data)
                print(f"\nFinal score: {score}/{total}")
                print(f"Learning data saved to: {LEARNING_FILE}")
                return

            if command == "p":
                pronounce_swedish(correct_answer)
                continue

            if command == "s":
                print(f"Skipped. Correct answer: {correct_answer}")
                pronounce_swedish(correct_answer)
                break

            if command == "k":
                increase_mastery(learning_data, key)
                save_learning_data(learning_data)

                new_mastery = get_mastery(learning_data, key)

                print(f"Marked as known. Mastery: {new_mastery}/{MAX_MASTERY}")
                print(f"Correct answer: {correct_answer}")
                break

            if command == "n":
                decrease_mastery(learning_data, key)
                save_learning_data(learning_data)

                new_mastery = get_mastery(learning_data, key)

                print(f"Marked for more practice. Mastery: {new_mastery}/{MAX_MASTERY}")
                print(f"Correct answer: {correct_answer}")
                pronounce_swedish(correct_answer)
                break

            total += 1

            if is_correct_answer(answer, correct_answer):
                print("Correct.")
                score += 1

                increase_mastery(learning_data, key)
                save_learning_data(learning_data)

                new_mastery = get_mastery(learning_data, key)
                print(f"Mastery increased to: {new_mastery}/{MAX_MASTERY}")

            else:
                print(f"Incorrect. Correct answer: {correct_answer}")
                pronounce_swedish(correct_answer)

                decrease_mastery(learning_data, key)
                save_learning_data(learning_data)

                new_mastery = get_mastery(learning_data, key)
                print(f"Mastery decreased to: {new_mastery}/{MAX_MASTERY}")

            break

        if question_limit is not None and questions_seen >= question_limit:
            save_learning_data(learning_data)
            print("\nQuiz complete.")
            print(f"Final score: {score}/{total}")
            print(f"Learning data saved to: {LEARNING_FILE}")
            return


# -----------------------------
# MENU
# -----------------------------

def choose_main_mode():
    """
    Main menu.
    """
    print("\nChoose mode:")
    print("1. Practice mode")
    print("2. Quiz mode")
    print("3. Practice first, then quiz")
    print("4. Show learning summary")
    print("5. Reset learning data")
    print("6. Exit")

    return input("\nEnter choice 1-6: ").strip()


def show_preview(df, number=10):
    """
    Shows a preview of the extracted verbs.
    """
    print("\nPreview of extracted verbs:")
    print("-----------------------------------")
    print(df.head(number).to_string(index=False))


def save_to_csv(df, output_path="swedish_verbs_extracted.csv"):
    """
    Saves the extracted table to CSV for checking or editing.
    """
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"\nSaved extracted verbs to: {output_path}")


# -----------------------------
# MAIN
# -----------------------------

def main():
    pdf_path = Path(PDF_PATH)

    if not pdf_path.exists():
        print(f"PDF not found: {PDF_PATH}")
        print("Put the PDF in the same folder as this script,")
        print("or change PDF_PATH in the code.")
        return

    print("Reading PDF...")
    df = read_verbs_from_pdf(PDF_PATH)

    show_preview(df)
    save_to_csv(df)

    while True:
        choice = choose_main_mode()

        if choice == "1":
            practice_mode(df)

        elif choice == "2":
            run_quiz(df)

        elif choice == "3":
            practice_mode(df)
            run_quiz(df)

        elif choice == "4":
            learning_data = load_learning_data()
            show_learning_summary(learning_data)

        elif choice == "5":
            reset_learning_data()

        elif choice == "6":
            print("Goodbye.")
            break

        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main()
