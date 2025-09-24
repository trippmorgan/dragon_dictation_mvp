#!/usr/bin/env python3
"""
Dragon-like Dictation Pro (Push-to-Talk + Macros + Slot-Filling)

What’s new vs. MVP:
- 🔑 Macro templates: Say "insert <macro_key>" (from config/macros.json).
- 🧩 Slot-filling: Say "set <field> to <value>" or "fill <field> <value>" to replace {field}.
- 🎯 Context biasing: Hotwords + current macro keywords are fed to the ASR for better accuracy.
- ✂️ Buffer mode: Text builds up in a buffer. You control when to paste.
- ✍️ Voice editing: "newline", "new paragraph", "period", "comma", "colon", "semicolon", "question mark".
- 🧠 Commands: "paste buffer", "scratch that", "clear buffer", "show fields", "undo paste".
- 🗂️ Session logs to data/logs/, with a unique file for each run.
- 🎨 Rich console output for better visual feedback.
- ⚙️ Automatic date insertion for `Procedure Date: {date}` fields in macros.

Dependencies (conda env recommended):
  - In your `dragon_dictation` conda env:
  - pip install faster-whisper sounddevice soundfile pynput pyperclip numpy rich python-dateutil

Author: ChatGPT
"""

import argparse
import json
import os
import re
import sys
import time
import tempfile
import threading
from datetime import datetime
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf
from dateutil.parser import parse as parse_date
from pynput import keyboard
from pynput.keyboard import Key, Controller as KeyController
import pyperclip
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

# Lazy import for faster-whisper
try:
    from faster_whisper import WhisperModel
except ImportError:
    print("\n[ERROR] faster-whisper not installed. In your conda env, run:\n  pip install faster-whisper\n", file=sys.stderr)
    sys.exit(1)

# --- Configuration ---
DEFAULT_SR = 16000
CHANNELS = 1
HOTKEY = keyboard.Key.f9
PASTE_DELAY_S = 0.1
CONFIG_DIR = Path("config")
DATA_DIR = Path("data")
LOG_DIR = DATA_DIR / "logs"

# --- Setup Console and Logging ---
console = Console()
LOG_DIR.mkdir(parents=True, exist_ok=True)
SESSION_TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = LOG_DIR / f"session_{SESSION_TIMESTAMP}.txt"

def log_message(message: str, to_console: bool = True):
    """Logs a message to the console and the session log file."""
    if to_console:
        console.print(message)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        # Strip rich formatting for clean log files
        clean_message = re.sub(r"\[.*?\]", "", message)
        f.write(f"[{datetime.now().isoformat()}] {clean_message}\n")

class Recorder:
    """A simple push-to-talk audio recorder."""
    def __init__(self, samplerate=DEFAULT_SR, channels=CHANNELS):
        self.samplerate = samplerate
        self.channels = channels
        self._recording = False
        self._frames = []
        self._stream = None

    def _callback(self, indata, frames, time_info, status):
        if status:
            log_message(f"[bold red]Audio Error: {status}[/bold red]")
        if self._recording:
            self._frames.append(indata.copy())

    def start_recording(self):
        if self._recording:
            return
        self._frames = []
        self._recording = True
        self._stream = sd.InputStream(
            samplerate=self.samplerate,
            channels=self.channels,
            callback=self._callback,
            dtype='float32'
        )
        self._stream.start()
        log_message("[bold green]Recording started...[/bold green] (Release to stop)")

    def stop_recording(self) -> str | None:
        if not self._recording:
            return None
        self._stream.stop()
        self._stream.close()
        self._recording = False
        log_message("[bold yellow]Recording stopped. Transcribing...[/bold yellow]")

        if not self._frames:
            log_message("[bold red]No audio data recorded.[/bold red]")
            return None

        audio_data = np.concatenate(self._frames, axis=0)
        temp_file = tempfile.mktemp(suffix=".wav", prefix="dictation_")
        sf.write(temp_file, audio_data, self.samplerate)
        return temp_file

class DictationApp:
    """Main application class to manage state and logic."""
    def __init__(self, model_size="small.en", device="auto", compute_type="default"):
        self.buffer = ""
        self.last_pasted_text = ""
        self.active_macro_key = None
        self.macros = self._load_json(CONFIG_DIR / "macros.json")
        self.hotwords = self._load_hotwords(CONFIG_DIR / "hotwords.txt")
        self.keyboard_controller = KeyController()
        self.recorder = Recorder()
        self.model = self._load_model(model_size, device, compute_type)

    def _load_model(self, model_size, device, compute_type):
        log_message(f"[cyan]Loading Whisper model '{model_size}'...[/cyan]")
        try:
            return WhisperModel(model_size, device=device, compute_type=compute_type)
        except Exception as e:
            log_message(f"[bold red]Error loading model: {e}[/bold red]")
            log_message("Please ensure you have a working PyTorch installation and the model files are accessible.")
            sys.exit(1)

    def _load_json(self, path: Path) -> dict:
        if not path.exists():
            log_message(f"[bold yellow]Warning: {path} not found. Macros will be disabled.[/bold yellow]")
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_hotwords(self, path: Path) -> list:
        if not path.exists():
            log_message(f"[bold yellow]Warning: {path} not found. Hotwords will be disabled.[/bold yellow]")
            return []
        with open(path, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]

    def get_contextual_prompt(self) -> str:
        """Generate a prompt for the ASR based on hotwords and the active macro."""
        prompt_parts = self.hotwords
        if self.active_macro_key and self.buffer:
            # Extract keywords from the current buffer/template
            macro_keywords = re.findall(r'[A-Z][a-z]+', self.buffer)
            prompt_parts.extend(macro_keywords)
        
        unique_prompts = sorted(list(set(p.lower() for p in prompt_parts)))
        return ", ".join(unique_prompts)

    def transcribe_audio(self, audio_path: str):
        """Transcribe audio file and process the resulting text."""
        initial_prompt = self.get_contextual_prompt()
        segments, _ = self.model.transcribe(
            audio_path,
            beam_size=5,
            initial_prompt=initial_prompt,
            word_timestamps=False,
        )
        os.remove(audio_path)
        
        full_text = "".join(segment.text for segment in segments).strip()
        log_message(f"[bold]Recognized:[/bold] [italic white]'{full_text}'[/italic white]")
        self.process_command(full_text)
        self.display_buffer()

    def process_command(self, text: str):
        """Process transcribed text for commands or append to buffer."""
        text_lower = text.lower().strip().replace(".", "")

        # --- High-priority commands ---
        if text_lower.startswith("insert "):
            macro_key = text_lower.split(" ", 1)[1].strip()
            self.insert_macro(macro_key)
        elif text_lower.startswith(("set ", "fill ")):
            self.fill_slot(text)
        elif text_lower == "scratch that":
            self.buffer = self.buffer.rsplit(' ', 2)[0] + ' ' if ' ' in self.buffer else ""
            log_message("[yellow]Scratched last phrase.[/yellow]")
        elif text_lower == "clear buffer":
            self.buffer = ""
            self.active_macro_key = None
            log_message("[bold yellow]Buffer cleared.[/bold yellow]")
        elif text_lower == "paste buffer":
            self.paste_text(self.buffer)
        elif text_lower == "undo paste":
            self.undo_last_paste()
        elif text_lower == "show fields":
            self.show_fields()
        else:
            # --- Text formatting and appending ---
            formatted_text = self._apply_formatting(text)
            self.buffer += formatted_text

    def _apply_formatting(self, text: str) -> str:
        """Apply spoken formatting commands."""
        replacements = {
            r"\bnewline\b": "\n",
            r"\bnew paragraph\b": "\n\n",
            r"\bcomma\b": ",",
            r"\bperiod\b": ".",
            r"\bcolon\b": ":",
            r"\bsemicolon\b": ";",
            r"\bquestion mark\b": "?",
        }
        
        # Add a space before appending unless buffer is empty or ends with newline/space
        prefix = "" if not self.buffer or self.buffer.endswith(("\n", " ")) else " "
        
        processed_text = text
        for pattern, replacement in replacements.items():
            processed_text = re.sub(pattern, replacement, processed_text, flags=re.IGNORECASE)
            
        return prefix + processed_text

    def insert_macro(self, key: str):
        """Insert a macro template into the buffer."""
        key = key.replace(" ", "_") # Allow "insert carotid art" for "carotid_art"
        if key in self.macros:
            self.buffer = self.macros[key]
            self.active_macro_key = key
            log_message(f"[bold magenta]Inserted macro: '{key}'[/bold magenta]")
            # Automatically fill the date
            if "{date}" in self.buffer:
                today_str = datetime.now().strftime("%B %d, %Y")
                self.buffer = self.buffer.replace("{date}", today_str)
                log_message(f"  -> Auto-filled date to [green]{today_str}[/green]")
            self.show_fields()
        else:
            log_message(f"[bold red]Macro '{key}' not found.[/bold red]")

    def fill_slot(self, text: str):
        """Fill a placeholder like {field} in the buffer."""
        match = re.match(r"(?:set|fill)\s+([\w\s]+?)\s+(?:to|is|as)\s+(.+)", text, re.IGNORECASE)
        if not match:
            match = re.match(r"(?:set|fill)\s+([\w\s]+)\s+(.+)", text, re.IGNORECASE) # Simpler version
        
        if match:
            field, value = match.groups()
            field = field.strip().replace(" ", "_")
            value = value.strip()
            
            # Smart Date Parsing
            if "date" in field.lower():
                try:
                    parsed_dt = parse_date(value)
                    value = parsed_dt.strftime("%B %d, %Y")
                except ValueError:
                    pass # Keep original value if parsing fails

            placeholder = f"{{{field}}}"
            if placeholder in self.buffer:
                self.buffer = self.buffer.replace(placeholder, value)
                log_message(f"  -> Filled [cyan]'{field}'[/cyan] with [green]'{value}'[/green]")
            else:
                log_message(f"[bold yellow]Warning: Field '{{{field}}}' not found in buffer.[/bold yellow]")
        else:
            log_message("[bold red]Invalid 'set/fill' command format.[/bold red] Use: 'set <field> to <value>'")

    def show_fields(self):
        """Display remaining fields in the buffer."""
        fields = re.findall(r"\{(\w+)\}", self.buffer)
        if fields:
            table = Table(title="Remaining Fields", style="magenta")
            table.add_column("Field Name", style="cyan")
            for field in set(fields):
                table.add_row(field)
            console.print(table)
        else:
            log_message("[bold green]All fields filled![/bold green]")

    def paste_text(self, text: str):
        """Copy text to clipboard and simulate a paste command."""
        if not text:
            log_message("[yellow]Nothing in buffer to paste.[/yellow]")
            return

        self.last_pasted_text = pyperclip.paste() # Save current clipboard
        pyperclip.copy(text)
        log_message(f"[bold blue]Pasting {len(text)} characters...[/bold blue]")
        time.sleep(PASTE_DELAY_S)
        
        paste_key = Key.cmd if sys.platform == 'darwin' else Key.ctrl
        self.keyboard_controller.press(paste_key)
        self.keyboard_controller.press('v')
        self.keyboard_controller.release('v')
        self.keyboard_controller.release(paste_key)

    def undo_last_paste(self):
        """Restore clipboard and simulate undo."""
        log_message("[yellow]Attempting to undo last paste...[/yellow]")
        if self.last_pasted_text:
            pyperclip.copy(self.last_pasted_text)

        undo_key = Key.cmd if sys.platform == 'darwin' else Key.ctrl
        self.keyboard_controller.press(undo_key)
        self.keyboard_controller.press('z')
        self.keyboard_controller.release('z')
        self.keyboard_controller.release(undo_key)

    def display_buffer(self):
        """Show the current buffer content in the console."""
        if not self.buffer.strip():
            return
        
        # Highlight remaining fields in yellow
        display_text = re.sub(r"(\{\w+\})", r"[bold yellow]\1[/bold yellow]", self.buffer)
        
        panel = Panel(
            Text(display_text, justify="left"),
            title="[bold cyan]Current Dictation Buffer[/bold cyan]",
            border_style="cyan",
            expand=False
        )
        console.print(panel)

def main():
    parser = argparse.ArgumentParser(description="Dragon-like Medical Dictation App")
    parser.add_argument("--model", default="small.en", help="Faster-Whisper model size (e.g., tiny.en, base.en, small.en)")
    parser.add_argument("--device", default="auto", help="Device for computation ('cpu', 'cuda', 'auto')")
    parser.add_argument("--compute_type", default="default", help="Compute type ('int8', 'float16', 'float32')")
    args = parser.parse_args()

    app = DictationApp(model_size=args.model, device=args.device, compute_type=args.compute_type)

    log_message("[bold]Dragon-like Dictation Pro[/bold] is running.", to_console=True)
    log_message(f" - [cyan]Model:[/cyan] {args.model}", to_console=True)
    log_message(f" - [cyan]Press and hold [bold magenta]'{HOTKEY.name.upper()}'[/bold magenta] to dictate.", to_console=True)
    log_message(f" - [cyan]Say '[bold]insert <macro_name>[/bold]' to start.", to_console=True)
    log_message(f" - [cyan]Press [bold magenta]'ESC'[/bold magenta] to quit.", to_console=True)
    log_message("-" * 20, to_console=True)

    def on_press(key):
        if key == HOTKEY and not app.recorder._recording:
            app.recorder.start_recording()

    def on_release(key):
        if key == HOTKEY and app.recorder._recording:
            audio_file = app.recorder.stop_recording()
            if audio_file:
                app.transcribe_audio(audio_file)
        if key == Key.esc:
            log_message("[bold]Exiting application.[/bold]")
            return False  # Stop the listener

    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()

if __name__ == "__main__":
    main()