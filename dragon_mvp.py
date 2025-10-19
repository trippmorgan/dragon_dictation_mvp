#!/usr/bin/env python3
"""
Dragon-like Dictation Pro (Version 5.0 - Gemini Client Edition)

What's New:
- ✨ Gemini Integration: Added a "process note" command to intelligently fill templates using a Gemini-powered backend.
- 🐞 Macro Fix: Correctly resolves the path to the 'config' directory, so macros now work reliably.
- 🧠 State Awareness: The client now remembers which macro is currently active to send for Gemini processing.

Author: ChatGPT & joevoldemort
"""
import json
import os
import re
import sys
import tempfile
import threading
import queue
from datetime import datetime
from pathlib import Path

# GUI Library
import tkinter as tk
from tkinter import scrolledtext

# Core Libraries
import numpy as np
import sounddevice as sd
import soundfile as sf
from pynput import keyboard
import pyperclip
import requests

# --- Configuration ---
DEFAULT_SR = 16000
CHANNELS = 1
TOGGLE_KEY = 'r'

# --- NEW, ROBUST PATHING FOR CONFIG ---
# This fixes the macro loading issue.
SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_DIR = SCRIPT_DIR / "config"

# --- MODIFIED: Added new Gemini endpoint ---
SERVER_BASE_URL = "http://100.101.184.20:5005"
TRANSCRIBE_URL = f"{SERVER_BASE_URL}/transcribe"
PROCESS_URL = f"{SERVER_BASE_URL}/process_note"


class DictationApp:
    def __init__(self):
        self.is_recording = False
        self.recorder = Recorder()
        self.macros = self._load_json(CONFIG_DIR / "macros.json")
        self.transcription_queue = queue.Queue()
        
        # --- NEW: State to track the active macro for Gemini ---
        self.active_macro_key = None

        print("Dragon Dictation Pro - Gemini Client")
        print(f"Connecting to backend server at: {SERVER_BASE_URL}")

        # --- GUI Setup ---
        self.root = tk.Tk()
        self.root.title("Medical Dictation Assistant (Gemini Client)")
        self.root.geometry("800x600")

        self.text_widget = scrolledtext.ScrolledText(self.root, wrap=tk.WORD, font=("Arial", 12))
        self.text_widget.pack(expand=True, fill='both', padx=10, pady=5)

        control_frame = tk.Frame(self.root)
        control_frame.pack(fill='x', padx=10, pady=5)
        
        self.status_label = tk.Label(control_frame, text="Status: Idle | Press 'r' to Record", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(side=tk.LEFT, expand=True, fill='x')

        copy_button = tk.Button(control_frame, text="Copy to Clipboard", command=self.copy_to_clipboard)
        copy_button.pack(side=tk.RIGHT)

    def _load_json(self, path: Path) -> dict:
        if not path.exists(): 
            print(f"[WARNING] Macros file not found at {path}", file=sys.stderr)
            return {}
        with open(path, "r", encoding="utf-8") as f: 
            return json.load(f)

    def copy_to_clipboard(self):
        text_to_copy = self.text_widget.get("1.0", tk.END)
        pyperclip.copy(text_to_copy)
        self.update_status("Text copied to clipboard!", "green")

    def toggle_recording(self):
        if self.is_recording:
            self.update_status("Sending to GPU server...", "orange")
            self.is_recording = False
            audio_file = self.recorder.stop_recording()
            if audio_file:
                threading.Thread(target=self.transcribe_audio_remote_thread, args=(audio_file,), daemon=True).start()
        else:
            self.update_status("Recording...", "red")
            self.is_recording = True
            self.recorder.start_recording()
            
    def transcribe_audio_remote_thread(self, audio_path: str):
        """Sends audio to the remote server for transcription."""
        try:
            with open(audio_path, 'rb') as f:
                files = {'file': (os.path.basename(audio_path), f, 'audio/wav')}
                response = requests.post(TRANSCRIBE_URL, files=files, timeout=20)
            response.raise_for_status()
            result = response.json()
            self.transcription_queue.put(result.get("text", "").strip())
        except Exception as e:
            error_message = f"ERROR: Transcription failed: {e}"
            print(error_message, file=sys.stderr)
            self.transcription_queue.put(error_message)
        finally:
            os.remove(audio_path)

    def process_note_remote_thread(self):
        """ --- NEW: Sends the current note text to Gemini for processing. --- """
        if not self.active_macro_key:
            self.transcription_queue.put("ERROR: No macro loaded to process.")
            return

        self.update_status("Asking Gemini to process note...", "blue")
        
        current_text = self.text_widget.get("1.0", tk.END).strip()
        payload = {
            "text": current_text,
            "macro_key": self.active_macro_key
        }

        try:
            response = requests.post(PROCESS_URL, json=payload, timeout=30) # Longer timeout for LLM
            response.raise_for_status()
            # Pass the JSON dictionary directly to the queue
            self.transcription_queue.put(response.json())
        except Exception as e:
            error_message = f"ERROR: Gemini processing failed: {e}"
            print(error_message, file=sys.stderr)
            self.transcription_queue.put(error_message)

    def process_queue(self):
        """Checks the queue for results and updates the GUI."""
        try:
            result = self.transcription_queue.get_nowait()
            
            # --- MODIFIED: Handle both text (from Whisper) and dict (from Gemini) ---
            if isinstance(result, str):
                self.process_command(result) # It's a transcribed text command
            elif isinstance(result, dict):
                self._reconstruct_note_from_json(result) # It's a filled template from Gemini
            
            self.update_status("Idle | Press 'r' to Record", "black")
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.process_queue)

    def process_command(self, text: str):
        """Processes transcribed text for commands or appends it."""
        if text.startswith("ERROR:"):
             self.update_status(text, "red")
             return

        text_lower_clean = text.lower().strip().replace(".", "").replace(",", "")
        
        # --- NEW: Command to trigger Gemini processing ---
        if text_lower_clean == "process note":
            threading.Thread(target=self.process_note_remote_thread, daemon=True).start()
            return

        # Command: insert <macro>
        if text_lower_clean.startswith("insert "):
            macro_key = text_lower_clean.split(" ", 1)[1].strip().replace(" ", "_")
            if macro_key in self.macros:
                # --- MODIFIED: Remember which macro is active ---
                self.active_macro_key = macro_key 
                template = self.macros[macro_key]
                if "{date}" in template:
                    template = template.replace("{date}", datetime.now().strftime("%B %d, %Y"))
                self.text_widget.delete("1.0", tk.END)
                self.text_widget.insert("1.0", template)
                self.update_status(f"Inserted macro: '{macro_key}'")
            return

        # Command: set <field> to <value> (still works as a fallback)
        match = re.match(r"(?:set|fill)\s+([\w\s]+?)\s+(?:to|is|as)\s+(.+)", text, re.IGNORECASE)
        if match:
            field, value = match.groups()
            placeholder = f"{{{field.strip().replace(' ', '_')}}}"
            current_text = self.text_widget.get("1.0", tk.END)
            if placeholder in current_text:
                new_text = current_text.replace(placeholder, value.strip(), 1)
                self.text_widget.delete("1.0", tk.END)
                self.text_widget.insert("1.0", new_text)
                self.update_status(f"Filled field '{field}'")
            return

        # No command, just append text
        self.text_widget.insert(tk.END, " " + text)

    def _reconstruct_note_from_json(self, data: dict):
        """ --- NEW: Updates the GUI with the filled template from Gemini. --- """
        if not self.active_macro_key or self.active_macro_key not in self.macros:
            return

        self.update_status("Note updated by Gemini!", "purple")
        
        # Start with the original template
        updated_text = self.macros[self.active_macro_key]
        if "{date}" in updated_text:
            updated_text = updated_text.replace("{date}", datetime.now().strftime("%B %d, %Y"))
        
        # Replace each placeholder with the value from the JSON
        for key, value in data.items():
            if value: # Only replace if Gemini returned a value
                updated_text = updated_text.replace(f"{{{key}}}", str(value))
        
        self.text_widget.delete("1.0", tk.END)
        self.text_widget.insert("1.0", updated_text)

    def update_status(self, message, color="black"):
        self.status_label.config(text=f"Status: {message}", fg=color)

    def start_app(self):
        listener_thread = threading.Thread(target=self.start_keyboard_listener, daemon=True)
        listener_thread.start()
        self.process_queue()
        print("GUI is running. The dictation window should be open.")
        print("Press 'r' in any application to toggle recording.")
        self.root.mainloop()

    def start_keyboard_listener(self):
        def on_press(key):
            try:
                if key.char == TOGGLE_KEY:
                    self.toggle_recording()
            except AttributeError:
                pass
        with keyboard.Listener(on_press=on_press) as listener:
            listener.join()

class Recorder:
    # ... (No changes to the Recorder class) ...
    def __init__(self, samplerate=DEFAULT_SR, channels=CHANNELS):
        self.samplerate = samplerate
        self.channels = channels
        self._frames = []
        self._stream = None
    def start_recording(self):
        self._frames = []
        self._stream = sd.InputStream(samplerate=self.samplerate, channels=self.channels, callback=lambda d, f, t, s: self._frames.append(d.copy()), dtype='float32')
        self._stream.start()
    def stop_recording(self) -> str | None:
        if not self._stream: return None
        self._stream.stop(); self._stream.close()
        if not self._frames: return None
        audio_data = np.concatenate(self._frames, axis=0)
        temp_file = tempfile.mktemp(suffix=".wav", prefix="dictation_")
        sf.write(temp_file, audio_data, self.samplerate)
        return temp_file

def main():
    app = DictationApp()
    app.start_app()

if __name__ == "__main__":
    main()