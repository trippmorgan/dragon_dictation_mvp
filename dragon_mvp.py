#!/usr/bin/env python3
"""
Dragon-like Dictation Pro (Version 4.0 - GPU Client Edition)

What's New:
- 🌐 Networked Transcription: Now sends audio to a dedicated GPU backend server.
- ⚡ Lightweight Client: No local Whisper model is loaded, making the GUI start instantly and use minimal resources.
- 🔧 Simplified Code: Removed local model management and related CLI arguments.
-  robust error handling for network issues.

Dependencies:
  - You will need to add the 'requests' library: `pip install requests`
  - All other dependencies from the previous version remain.

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
import requests # <-- ADDED for network requests

# --- Configuration ---
DEFAULT_SR = 16000
CHANNELS = 1
TOGGLE_KEY = 'r'
CONFIG_DIR = Path("config")

# IMPORTANT: This is the Tailscale IP of your GPU server.
SERVER_URL = "http://100.101.184.20:5005/transcribe"
USE_REMOTE = True

class DictationApp:
    def __init__(self):
        self.is_recording = False
        self.recorder = Recorder()
        self.macros = self._load_json(CONFIG_DIR / "macros.json")
        self.hotwords = self._load_hotwords(CONFIG_DIR / "hotwords.txt") # This can be removed if you handle prompts server-side
        self.transcription_queue = queue.Queue()

        print("Dragon Dictation Pro - GPU Client")
        print(f"Connecting to backend server at: {SERVER_URL}")

        # --- GUI Setup ---
        self.root = tk.Tk()
        self.root.title("Medical Dictation Assistant (GPU Client)")
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
        if not path.exists(): return {}
        with open(path, "r", encoding="utf-8") as f: return json.load(f)

    def _load_hotwords(self, path: Path) -> list:
        if not path.exists(): return []
        with open(path, "r", encoding="utf-8") as f: return [line.strip() for line in f if line.strip()]

    def copy_to_clipboard(self):
        text_to_copy = self.text_widget.get("1.0", tk.END)
        pyperclip.copy(text_to_copy)
        self.update_status("Text copied to clipboard!", "green")

    def toggle_recording(self):
        if self.is_recording:
            # --- Stop Recording ---
            self.update_status("Sending to GPU server...", "orange")
            self.is_recording = False
            audio_file = self.recorder.stop_recording()
            if audio_file:
                # Transcribe on the remote server in a separate thread
                threading.Thread(target=self.transcribe_audio_remote_thread, args=(audio_file,), daemon=True).start()
        else:
            # --- Start Recording ---
            self.update_status("Recording...", "red")
            self.is_recording = True
            self.recorder.start_recording()
            
    def transcribe_audio_remote_thread(self, audio_path: str):
        """Sends audio to the remote server and puts the result in the queue."""
        try:
            with open(audio_path, 'rb') as f:
                files = {'file': (os.path.basename(audio_path), f, 'audio/wav')}
                response = requests.post(SERVER_URL, files=files, timeout=20) # 20-second timeout

            response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)

            result = response.json()
            full_text = result.get("text", "").strip()
            self.transcription_queue.put(full_text)

        except requests.exceptions.RequestException as e:
            error_message = f"ERROR: Could not connect to server: {e}"
            print(error_message, file=sys.stderr)
            self.transcription_queue.put(error_message)
        except Exception as e:
            error_message = f"ERROR: An unexpected error occurred: {e}"
            print(error_message, file=sys.stderr)
            self.transcription_queue.put(error_message)
        finally:
            # Clean up the temporary audio file
            os.remove(audio_path)
    
    def process_queue(self):
        """Checks the queue for transcribed text and updates the GUI."""
        try:
            text = self.transcription_queue.get_nowait()
            self.process_command(text)
            self.update_status("Idle | Press 'r' to Record", "black")
        except queue.Empty:
            pass # No new transcriptions
        finally:
            self.root.after(100, self.process_queue) # Check again in 100ms

    def process_command(self, text: str):
        """Processes the transcribed text for commands or appends it."""
        if text.startswith("ERROR:"):
             self.update_status(text, "red")
             return

        # Clean the text for better command matching
        text_lower_clean = text.lower().strip().replace(".", "").replace(",", "")
        
        # Command: insert <macro>
        if text_lower_clean.startswith("insert "):
            macro_key = text_lower_clean.split(" ", 1)[1].strip().replace(" ", "_")
            if macro_key in self.macros:
                template = self.macros[macro_key]
                if "{date}" in template:
                    template = template.replace("{date}", datetime.now().strftime("%B %d, %Y"))
                self.text_widget.delete("1.0", tk.END)
                self.text_widget.insert("1.0", template)
                self.update_status(f"Inserted macro: '{macro_key}'")
                return

        # Command: set <field> to <value>
        match = re.match(r"(?:set|fill)\s+([\w\s]+?)\s+(?:to|is|as)\s+(.+)", text, re.IGNORECASE)
        if match:
            field, value = match.groups()
            field = field.strip().replace(" ", "_")
            value = value.strip()
            placeholder = f"{{{field}}}"
            
            current_text = self.text_widget.get("1.0", tk.END)
            if placeholder in current_text:
                new_text = current_text.replace(placeholder, value, 1)
                self.text_widget.delete("1.0", tk.END)
                self.text_widget.insert("1.0", new_text)
                self.update_status(f"Filled field '{field}'")
            return

        # No command, just append text
        self.text_widget.insert(tk.END, " " + text)

    def update_status(self, message, color="black"):
        self.status_label.config(text=f"Status: {message}", fg=color)

    def start_app(self):
        """Starts the keyboard listener and the GUI main loop."""
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
    """A simple audio recorder."""
    def __init__(self, samplerate=DEFAULT_SR, channels=CHANNELS):
        self.samplerate = samplerate
        self.channels = channels
        self._frames = []
        self._stream = None

    def start_recording(self):
        self._frames = []
        self._stream = sd.InputStream(
            samplerate=self.samplerate,
            channels=self.channels,
            callback=lambda d, f, t, s: self._frames.append(d.copy()),
            dtype='float32'
        )
        self._stream.start()

    def stop_recording(self) -> str | None:
        if not self._stream: return None
        self._stream.stop()
        self._stream.close()

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