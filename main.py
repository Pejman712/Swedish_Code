import csv
import json
import random
import os
import hashlib
import threading
import urllib.parse
from pathlib import Path

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import StringProperty
from kivy.clock import Clock

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from android.runnable import run_on_ui_thread as _ui_thread
    ON_ANDROID = True
except Exception:
    ON_ANDROID = False
    def _ui_thread(fn):
        return fn


SWEDISH_FORMS = [
    "Presens",
    "Infinitiv",
    "Imperativ",
    "Past tense",
    "Present perfect tense",
]

DEFAULT_MASTERY = 2
MIN_MASTERY = 0
MAX_MASTERY = 5


def normalize_answer(text):
    return " ".join(text.lower().strip().rstrip("!").split())


def is_correct_answer(user_answer, correct_answer):
    user_answer = normalize_answer(user_answer)
    return user_answer in [
        normalize_answer(part)
        for part in correct_answer.split("/")
    ]


def make_learning_key(item, tense):
    return f"{item['English translation']} | {tense} | {item[tense]}"


class TrainerRoot(BoxLayout):
    question = StringProperty("")
    tense = StringProperty("")
    feedback = StringProperty("")
    answer_hint = StringProperty("")
    tts_status = StringProperty("TTS: ready (online)")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.app_dir = Path(App.get_running_app().user_data_dir)
        self.learning_file = self.app_dir / "swedish_learning_weights.json"
        self._sound = None
        self._history = []

        self.verbs = self.load_verbs()
        self.learning_data = self.load_learning_data()

        self.current_item = None
        self.current_tense = None

        self.next_question()

    # ------------------------------------------------------------------
    # Swipe gestures
    # ------------------------------------------------------------------

    def on_touch_down(self, touch):
        touch.ud['start_x'] = touch.x
        touch.ud['start_y'] = touch.y
        touch.grab(self)
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            dx = touch.x - touch.ud.get('start_x', touch.x)
            dy = touch.y - touch.ud.get('start_y', touch.y)

            if abs(dx) > 100 and abs(dx) > abs(dy):
                if dx > 0:  # swipe right → next word
                    self.ids.answer.text = ""
                    self.next_question()
                else:         # swipe left → previous word
                    self.previous_question()
                return True
            elif abs(dy) > 100 and abs(dy) > abs(dx):
                if dy > 0:   # swipe up → repeat Swedish
                    self.pronounce_current()
                else:         # swipe down → speak English
                    self.speak_english()
                return True

        return super().on_touch_up(touch)

    # ------------------------------------------------------------------
    # TTS
    # ------------------------------------------------------------------

    def _cache_path(self, text, lang='sv'):
        h = hashlib.md5(f"{lang}:{text}".encode()).hexdigest()[:10]
        return str(self.app_dir / f"tts_{h}.mp3")

    def speak(self, text):
        if not text or text == '-':
            return
        threading.Thread(
            target=self._download_and_play, args=(text, 'sv'), daemon=True
        ).start()

    def speak_english(self):
        if not self.current_item:
            return
        text = self.current_item['English translation']
        threading.Thread(
            target=self._download_and_play, args=(text, 'en'), daemon=True
        ).start()

    def _download_and_play(self, text, lang='sv'):
        cache = self._cache_path(text, lang)

        if not os.path.exists(cache):
            if not HAS_REQUESTS:
                Clock.schedule_once(
                    lambda dt: setattr(self, 'tts_status', 'TTS: requests missing'), 0
                )
                return
            Clock.schedule_once(
                lambda dt: setattr(self, 'tts_status', f'TTS: downloading "{text}"...'), 0
            )
            try:
                url = "https://translate.google.com/translate_tts"
                params = {'ie': 'UTF-8', 'q': text, 'tl': lang, 'client': 'tw-ob'}
                headers = {'User-Agent': 'Mozilla/5.0 (Linux; Android 10)'}
                r = requests.get(url, params=params, headers=headers, timeout=6)
                Clock.schedule_once(
                    lambda dt: setattr(self, 'tts_status',
                                       f'TTS: HTTP {r.status_code}, {len(r.content)} bytes'), 0
                )
                if r.status_code != 200:
                    return
                with open(cache, 'wb') as f:
                    f.write(r.content)
            except Exception as e:
                Clock.schedule_once(
                    lambda dt: setattr(self, 'tts_status', f'TTS download error: {e}'), 0
                )
                return
        else:
            Clock.schedule_once(
                lambda dt: setattr(self, 'tts_status', 'TTS: playing (cached)'), 0
            )

        Clock.schedule_once(lambda dt: self._play(cache), 0)

    def _play(self, path):
        try:
            from kivy.core.audio import SoundLoader
            if self._sound:
                self._sound.stop()
                self._sound.unload()
            self._sound = SoundLoader.load(path)
            if self._sound:
                self._sound.play()
                self.tts_status = 'TTS: playing'
            else:
                self.tts_status = 'TTS: could not load audio'
        except Exception as e:
            self.tts_status = f'Play error: {e}'

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def load_verbs(self):
        path = Path(__file__).parent / "data" / "swedish_verbs_extracted.csv"
        with open(path, newline="", encoding="utf-8-sig") as file:
            return list(csv.DictReader(file))

    def load_learning_data(self):
        if not self.learning_file.exists():
            return {}
        try:
            with open(self.learning_file, "r", encoding="utf-8") as file:
                data = json.load(file)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def save_learning_data(self):
        self.app_dir.mkdir(parents=True, exist_ok=True)
        with open(self.learning_file, "w", encoding="utf-8") as file:
            json.dump(self.learning_data, file, ensure_ascii=False, indent=2)

    def get_mastery(self, key):
        try:
            value = int(self.learning_data.get(key, DEFAULT_MASTERY))
        except Exception:
            value = DEFAULT_MASTERY
        return max(MIN_MASTERY, min(MAX_MASTERY, value))

    def set_mastery(self, key, value):
        self.learning_data[key] = max(MIN_MASTERY, min(MAX_MASTERY, value))
        self.save_learning_data()

    def choose_weighted_item(self):
        candidates = []
        for item in self.verbs:
            form_masteries = []
            for tense in SWEDISH_FORMS:
                value = item.get(tense, "")
                if not value or value == "-":
                    continue
                key = make_learning_key(item, tense)
                form_masteries.append(self.get_mastery(key))
            if not form_masteries:
                continue
            weakest = min(form_masteries)
            weight = (MAX_MASTERY + 1) - weakest
            candidates.append((item, weight))

        items = [item for item, _ in candidates]
        weights = [weight for _, weight in candidates]
        return random.choices(items, weights=weights, k=1)[0]

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def next_question(self):
        if self.current_item and self.current_tense:
            self._history.append((self.current_item, self.current_tense))
            if len(self._history) > 30:
                self._history.pop(0)

        self.current_item = self.choose_weighted_item()
        valid_tenses = [
            tense for tense in SWEDISH_FORMS
            if self.current_item.get(tense) and self.current_item.get(tense) != "-"
        ]
        self.current_tense = random.choice(valid_tenses)
        self.question = f"English: {self.current_item['English translation']}"
        self.tense = f"Form: {self.current_tense}"
        self.feedback = ""
        self.answer_hint = ""
        Clock.schedule_once(lambda dt: self.pronounce_current(), 0.3)

    def previous_question(self):
        if not self._history:
            self.feedback = "No previous word."
            return
        self.current_item, self.current_tense = self._history.pop()
        self.question = f"English: {self.current_item['English translation']}"
        self.tense = f"Form: {self.current_tense}"
        self.feedback = ""
        self.answer_hint = ""
        Clock.schedule_once(lambda dt: self.pronounce_current(), 0.3)

    def pronounce_current(self):
        if self.current_item and self.current_tense:
            self.speak(self.current_item.get(self.current_tense, ""))

    def check_answer(self, user_answer):
        correct = self.current_item[self.current_tense]
        key = make_learning_key(self.current_item, self.current_tense)

        if is_correct_answer(user_answer, correct):
            self.set_mastery(key, self.get_mastery(key) + 1)
            self.feedback = "Correct."
        else:
            self.set_mastery(key, self.get_mastery(key) - 1)
            self.feedback = f"Incorrect. Answer: {correct}"
            self.speak(correct)

    def reveal_answer(self):
        self.answer_hint = self.current_item[self.current_tense]
        self.speak(self.answer_hint)


class SwedishTrainerApp(App):
    def build(self):
        return TrainerRoot()


if __name__ == "__main__":
    SwedishTrainerApp().run()
