# --------------------------------------------------------------------------------------------------------
# - pyw - will run without terminal window
# - Pre-req vvv---
# - pip install customtkinter google-genai sounddevice scipy keyboard pyperclip pyautogui faster-whisper
#
# --------------------------------------------------------------------------------------------------------
# C:\Users\moshe\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup
# C:\Users\moshe\PyCharmMiscProject\Voice_typing
#
# --------------------------------------------------------------------------------------------------------
# טיפ: פתיחה אוטומטית עם הדלקת המחשב
# אם תרצה שהחלונית תיפתח לבד בכל פעילה מחדש של המחשב:
#לחץ על מקשי המקלדת Win + R (נפתח חלון "הפעל").
#הקלד shell:startup ולחץ Enter (זה יפתח את תיקיית ההפעלה האוטומטית של ווינדוס).
#צור קיצור דרך לקובץ ה-voice_typer_gui.pyw שלך (לחץ עליו מקש ימני -> שלח אל -> צור קיצור דרך).
#גרור את קיצור הדרך אל תוך תיקיית ה-Startup שנפתחה.
# --------------------------------------------------------------------------------------------------------

# https://aistudio.google.com/api-keys
# API key is read from the GEMINI_API_KEY user environment variable (never put it in this file).
# Win+R  -  powershell
# [Environment]::SetEnvironmentVariable('GEMINI_API_KEY', '<key>', 'User')

# --------------------------------------------------------------------------------------------------------
#  Code start Here:
# --------------------------------------------------------------------------------------------------------
# --------------------------------------------------------------------------------------------------------
# --------------------------------------------------------------------------------------------------------

import os
import time
import threading
import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write
import keyboard
import pyperclip
import customtkinter as ctk
from google import genai

HOTKEY = "ctrl+alt+space"
SAMPLE_RATE = 16000
TEMP_AUDIO_FILE = "temp_recording.wav"
# Models tried in order (one per attempt). Lite is fast and less often overloaded; full flash is the backup.
MODEL_ATTEMPTS = ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.5-flash-lite"]
REQUEST_TIMEOUT_MS = 30000

# אתחול Gemini API
API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    raise SystemExit("GEMINI_API_KEY environment variable is not set")
client = genai.Client(api_key=API_KEY, http_options={"timeout": REQUEST_TIMEOUT_MS})

# --- עיצוב החלונית הצפה ---
BG = "#1e1e1e"
FG_DIM = "#9a9a9a"
BLUE, BLUE_HOVER = "#1f6fd1", "#1859a8"
RED, RED_HOVER = "#e0443e", "#b83631"
ORANGE, GREEN = "#f39c12", "#2ecc71"
READY_TEXT = "Ctrl+Alt+Space"


class VoiceTyperApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("dark")
        self.title("Voice Typer")
        self.overrideredirect(True)          # בלי פס כותרת
        self.attributes("-topmost", True)    # תמיד מעל חלונות אחרים
        self.attributes("-alpha", 0.94)
        self.configure(fg_color=BG)

        self.is_recording = False
        self.audio_frames = []
        self._blink_on = False

        # כפתור מיקרופון עגול
        self.toggle_btn = ctk.CTkButton(
            self, text="🎙", width=34, height=34, corner_radius=17, border_spacing=0,
            font=ctk.CTkFont(size=16), fg_color=BLUE, hover_color=BLUE_HOVER,
            command=self.toggle_recording_gui,
        )
        self.toggle_btn.pack(side="left", padx=(8, 6), pady=7)

        # שורת סטטוס
        self.status_label = ctk.CTkLabel(
            self, text=READY_TEXT, text_color=FG_DIM, anchor="w", width=110,
            font=ctk.CTkFont(size=12),
        )
        self.status_label.pack(side="left", padx=(0, 4))

        # כפתור סגירה קטן
        self.close_btn = ctk.CTkButton(
            self, text="✕", width=22, height=22, corner_radius=11,
            fg_color="transparent", hover_color="#3a3a3a", text_color=FG_DIM,
            font=ctk.CTkFont(size=11), command=self.quit_app,
        )
        self.close_btn.pack(side="right", padx=(0, 6))

        # גרירת החלונית בעזרת העכבר (על הרקע או על הטקסט)
        for w in (self, self.status_label):
            w.bind("<ButtonPress-1>", self._start_drag)
            w.bind("<B1-Motion>", self._on_drag)

        self._place_bottom_right()
        self.after(10, self._apply_windows_style)

        # הפעלת האזנה לקיצור מקשים ברקע
        keyboard.add_hotkey(HOTKEY, self.toggle_recording_hotkey)

        # התחלת תהליך האזנה למיקרופון ברקע
        self.stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype='int16',
            callback=self.audio_callback
        )
        self.stream.start()

    # ---------- חלון ----------
    def _apply_windows_style(self):
        """פינות מעוגלות (Windows 11), בלי כפתור בשורת המשימות, ולחיצה שלא גונבת פוקוס."""
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            GWL_EXSTYLE, WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW = -20, 0x08000000, 0x00000080
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)
            pref = ctypes.c_int(2)  # DWMWCP_ROUND
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(pref), ctypes.sizeof(pref))
        except Exception as e:
            print(f"Window style not applied: {e}")

    def _place_bottom_right(self):
        """גודל לפי התוכן, ומיקום בפינה ימנית-תחתונה לפי הגודל האמיתי (מתחשב בהגדלת תצוגה)."""
        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        margin = 16
        x = self.winfo_screenwidth() - w - margin
        y = self.winfo_screenheight() - h - margin - 48  # מעל שורת המשימות
        self.wm_geometry(f"+{x}+{y}")  # tk ישיר, בלי שינוי קנה מידה של customtkinter

    def _start_drag(self, event):
        self._drag_dx = event.x_root - self.winfo_x()
        self._drag_dy = event.y_root - self.winfo_y()

    def _on_drag(self, event):
        self.geometry(f"+{event.x_root - self._drag_dx}+{event.y_root - self._drag_dy}")

    def quit_app(self):
        try:
            self.stream.stop()
            keyboard.unhook_all_hotkeys()
        finally:
            self.destroy()

    def set_status(self, text, color=FG_DIM):
        self.status_label.configure(text=text, text_color=color)

    def _blink(self):
        if not self.is_recording:
            return
        self._blink_on = not self._blink_on
        self.toggle_btn.configure(fg_color=RED if self._blink_on else RED_HOVER)
        self.after(500, self._blink)

    # ---------- הקלטה ----------
    def audio_callback(self, indata, frames, time_info, status):
        if self.is_recording:
            self.audio_frames.append(indata.copy())

    def toggle_recording_hotkey(self):
        self.after(0, self.toggle_recording_gui)

    def toggle_recording_gui(self):
        if not self.is_recording:
            self.audio_frames = []
            self.is_recording = True
            self.set_status("● מקליט...", RED)
            self.toggle_btn.configure(text="■", fg_color=RED, hover_color=RED_HOVER)
            self._blink()
        else:
            self.is_recording = False
            self.toggle_btn.configure(text="🎙", fg_color=BLUE, hover_color=BLUE_HOVER)

            if self.audio_frames:
                self.set_status("מתמלל...", ORANGE)
                self.toggle_btn.configure(state="disabled")
                recording = np.concatenate(self.audio_frames, axis=0)
                write(TEMP_AUDIO_FILE, SAMPLE_RATE, recording)
                threading.Thread(target=self.process_audio, daemon=True).start()
            else:
                self.set_status(READY_TEXT)

    def process_audio(self):
        text = ""
        error = None
        for attempt, model in enumerate(MODEL_ATTEMPTS):
            try:
                print(f"שולח נתונים ל-Gemini (ניסיון {attempt + 1}, {model})...")

                with open(TEMP_AUDIO_FILE, "rb") as f:
                    audio_bytes = f.read()

                response = client.models.generate_content(
                    model=model,
                    contents=[
                        {
                            "role": "user",
                            "parts": [
                                {"text": "תמלל את ההקלטה הבאה במדויק. הדובר עשוי לדבר בעברית, באנגלית, או לשלב ביניהן. הוסף סימני פיסוק נכונים והחזר אך ורק את הטקסט המתומלל ללא שום הקדמות."},
                                {"inline_data": {"mime_type": "audio/wav", "data": audio_bytes}}
                            ]
                        }
                    ]
                )

                text = (response.text or "").strip()
                if text:
                    break  # הצליח, יוצא מהלופ

            except Exception as e:
                error = e
                print(f"ניסיון {attempt + 1} נכשל: {str(e)}")
                if attempt < len(MODEL_ATTEMPTS) - 1:
                    time.sleep(1.5)

        if text:
            print(f"תמלול הצליח: {text}")

            # הדבקה אוטומטית למקום שבו הסמן נמצא
            old_clipboard = pyperclip.paste()
            pyperclip.copy(text + " ")
            time.sleep(0.2)
            keyboard.send("ctrl+v")
            time.sleep(0.2)
            pyperclip.copy(old_clipboard)

        if os.path.exists(TEMP_AUDIO_FILE):
            os.remove(TEMP_AUDIO_FILE)

        self.after(0, lambda: self.toggle_btn.configure(state="normal"))
        if text:
            self.after(0, lambda: self.set_status("✓ הודבק", GREEN))
        else:
            self.after(0, lambda: self.set_status("✕ שגיאה - נסה שוב", RED))
            print(f"תמלול נכשל: {error}")
        self.after(2500, lambda: self.set_status(READY_TEXT) if not self.is_recording else None)


if __name__ == "__main__":
    app = VoiceTyperApp()
    app.mainloop()
