# Voice Typer

A small floating bar for Windows that types what you say. Press a hotkey, speak (Hebrew, English, or a mix of both), press it again, and the transcribed text is pasted wherever your cursor is.

Transcription is done by Google's Gemini API.

## Features

- **Global hotkey:** `Ctrl+Alt+Space` starts and stops recording from any app.
- **Automatic paste:** the text is pasted into the active window, and your previous clipboard text is restored.
- **Hebrew and English:** mixed-language speech, with punctuation added.
- **Compact floating bar:** always on top, draggable, with rounded corners and no taskbar button. Clicking it doesn't steal focus from the window you're typing in.
- **Model fallback:** tries `gemini-3.5-flash-lite` first, which is fast and less often overloaded, then `gemini-3.8-flash`. Each request times out after 30 seconds.
- **Privacy info:** the **i** button on the bar shows what data is sent where.

## Requirements

- Windows 10 or 11
- Python 3.10+
- A microphone
- A Gemini API key from [Google AI Studio](https://aistudio.google.com/api-keys)

## Installation

```powershell
pip install customtkinter google-genai sounddevice scipy numpy keyboard pyperclip
```

## API key setup

The key is read from the `GEMINI_API_KEY` environment variable. **Never put the key in the code.**

1. Create a key at <https://aistudio.google.com/api-keys>.
2. Open **Windows PowerShell** and run this, replacing the placeholder with your key:
   ```powershell
   [Environment]::SetEnvironmentVariable('GEMINI_API_KEY', 'PASTE-YOUR-KEY-HERE', 'User')
   ```
   `'User'` is literal: it saves the variable for your Windows account. Don't replace it with your username.
3. Restart any open terminals or IDEs so they see the new variable.

## Running

Double-click `voice_typer_gui.pyw`, which runs with no console window.

To see log output while debugging, run it with Python instead:

```powershell
python voice_typer_gui.pyw
```

## Usage

| Action | How |
|---|---|
| Start / stop recording | `Ctrl+Alt+Space` or click the blue mic button |
| Move the bar | Drag its background or text |
| Privacy info | Click **i** |
| Quit | Click **✕** |

Status messages on the bar:
- **● מקליט...**: recording. The button blinks red.
- **מתמלל...**: transcribing.
- **✓ הודבק**: the text was pasted.
- **✕ שגיאה - נסה שוב**: transcription failed. Try again.

## Start automatically with Windows

1. Press `Win+R`, type `shell:startup`, and press Enter.
2. Right-click `voice_typer_gui.pyw` → **Send to** → **Desktop (create shortcut)**.
3. Move the shortcut into the Startup folder that opened.

## Privacy

Your recordings are sent to Google for transcription. On the **free tier** of the Gemini API, Google may use that data to improve its products, and human reviewers may read it. Don't dictate sensitive information on the free tier.

The full notice is at the top of `voice_typer_gui.pyw`, and the **i** button in the app shows the same text. It covers the microphone, the keyboard hook, the clipboard, the temporary audio file and the API key.

## Cost

Switching from the free to the paid tier has no fee. Usage costs roughly $0.0015 per minute of speech. See [`readme.paid_price.txt`](readme.paid_price.txt) for details, and check Google's [current pricing](https://ai.google.dev/gemini-api/docs/pricing).

## Troubleshooting

| Problem | Fix |
|---|---|
| App exits immediately with `GEMINI_API_KEY environment variable is not set` | Set the key (see [API key setup](#api-key-setup)), then restart your terminal or IDE. |
| `✕ שגיאה` with `503 UNAVAILABLE` in the log | Google's servers are overloaded. Wait a minute and try again. |
| `404 NOT_FOUND ... no longer available` | Google retired a model. Update `MODEL_ATTEMPTS` near the top of the file. |
| `401 API key not valid` | The key was deleted or mistyped. Create a new one and set it again. |
| Text pastes into the wrong place | The text goes to whichever window is active when transcription finishes. Keep your cursor in place. |
| Hotkey doesn't work in some apps | Apps running as administrator can block it. Run Voice Typer as administrator too, or click the mic button. |

## Configuration

Settings at the top of `voice_typer_gui.pyw`:

| Setting | Default | Meaning |
|---|---|---|
| `HOTKEY` | `ctrl+alt+space` | Global start/stop shortcut |
| `MODEL_ATTEMPTS` | lite → flash → lite | Models tried in order, one per attempt |
| `REQUEST_TIMEOUT_MS` | `30000` | Timeout for each request |
| `SAMPLE_RATE` | `16000` | Recording sample rate (Hz) |
