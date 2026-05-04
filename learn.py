import random
import re
import asyncio
import os
from pathlib import Path

import pdfplumber
import pandas as pd
import edge_tts
from playsound import playsound


# -----------------------------
# SETTINGS
# -----------------------------

PDF_PATH = "./swedish_verbs_table_v3.pdf"

SWEDISH_VOICE = "sv-SE-SofieNeural"
AUDIO_FILE = "swedish_word.mp3"

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
# PRACTICE MODE
# -----------------------------

def practice_mode(df):
    """
    Shows each verb with all Swedish forms.
    Lets the user listen to pronunciation before moving on.
    """
    if df.empty:
        print("No verbs found.")
        return

    records = df.to_dict(orient="records")
    random.shuffle(records)

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
    print("q = quit practice")
    print("-----------------------------------")

    for item in records:
        while True:
            print("\n===================================")
            print(f"English: {item['English translation']}")
            print("-----------------------------------")
            print(f"1. Presens:                {item['Presens']}")
            print(f"2. Infinitiv:              {item['Infinitiv']}")
            print(f"3. Imperativ:              {item['Imperativ']}")
            print(f"4. Past tense:             {item['Past tense']}")
            print(f"5. Present perfect tense:  {item['Present perfect tense']}")

            command = input("\nChoose pronunciation, Enter for next, or q: ").strip().lower()

            if command == "q":
                print("Practice ended.")
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

            print("Unknown command.")


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


def run_quiz(df):
    """
    Runs the Swedish verb quiz.
    """
    if df.empty:
        print("No verbs found in the PDF.")
        return

    print(f"\nLoaded {len(df)} verbs from the PDF.")

    selected_tenses = choose_quiz_mode()

    print("\nQuiz commands:")
    print("q = quit")
    print("p = hear pronunciation again")
    print("s = skip")
    print()

    records = df.to_dict(orient="records")
    random.shuffle(records)

    score = 0
    total = 0

    for item in records:
        english = item["English translation"]

        tense = random.choice(selected_tenses)
        correct_answer = item[tense]

        if not correct_answer or correct_answer == "-":
            continue

        print("-----------------------------------")
        print(f"English: {english}")
        print(f"Tense/form: {tense}")

        pronounce_swedish(correct_answer)

        while True:
            answer = input("Swedish: ").strip()

            if answer.lower() == "q":
                print(f"\nFinal score: {score}/{total}")
                return

            if answer.lower() == "p":
                pronounce_swedish(correct_answer)
                continue

            if answer.lower() == "s":
                print(f"Skipped. Correct answer: {correct_answer}")
                pronounce_swedish(correct_answer)
                break

            total += 1

            if is_correct_answer(answer, correct_answer):
                print("Correct.")
                score += 1
            else:
                print(f"Incorrect. Correct answer: {correct_answer}")
                pronounce_swedish(correct_answer)

            break

    print("\nQuiz complete.")
    print(f"Final score: {score}/{total}")


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
    print("4. Exit")

    return input("\nEnter choice 1-4: ").strip()


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
            print("Goodbye.")
            break

        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main()
