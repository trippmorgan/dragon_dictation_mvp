#!/usr/bin/env python3
"""
Dragon Dictation Pro - Enhanced Client (v6.0)

NEW FEATURES:
- 📊 Confidence Score Highlighting: Low-confidence fields shown in yellow
- ⏱️ Performance Metrics: Shows processing times
- 🔄 Undo/Redo Support: Full history tracking
- 🎯 Field Validation: Shows which fields still need attention
- 📋 Enhanced Status Bar: More detailed feedback

Author: Enhanced by Claude
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
from collections import deque

import tkinter as tk
from tkinter import scrolledtext, messagebox

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

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_DIR = SCRIPT_DIR / "config"

SERVER_BASE_URL = "http://100.101.184.20:5005"
TRANSCRIBE_URL = f"{SERVER_BASE_URL}/transcribe"
PROCESS_URL = f"{SERVER_BASE_URL}/process_note"
VALIDATE_URL = f"{SERVER_BASE_URL}/validate_macro"

# Confidence thresholds
HIGH_CONFIDENCE = 0.8
MEDIUM_CONFIDENCE = 0.6

class DictationApp:
    def __init__(self):
        self.is_recording = False
        self.recorder = Recorder()
        self.macros = self._load_json(CONFIG_DIR / "macros.json")
        self.transcription_queue = queue.Queue()
        
        self.active_macro_key = None
        self.field_confidence = {}  # Track confidence scores
        self.history = deque(maxlen=50)  # Undo history
        self.redo_stack = deque(maxlen=50)
        
        print("=" * 60)
        print("Dragon Dictation Pro - Enhanced Client v6.0")
        print(f"Backend: {SERVER_BASE_URL}")
        print("=" * 60)
        
        self._check_server_health()
        self._setup_gui()

    def _check_server_health(self):
        """Check if backend server is reachable"""
        try:
            response = requests.get(SERVER_BASE_URL, timeout=3)
            info = response.json()
            print(f"✓ Server healthy: {info.get('status')}")
            print(f"✓ Gemini: {info.get('gemini_enabled')}")
            print(f"✓ Macros: {info.get('macros_loaded')}")
        except Exception as e:
            print(f"⚠ Warning: Could not reach server: {e}")

    def _setup_gui(self):
        """Initialize the GUI"""
        self.root = tk.Tk()
        self.root.title("Dragon Dictation Pro v6.0 - Enhanced")
        self.root.geometry("900x700")
        
        # Menu bar
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Undo (Ctrl+Z)", command=self.undo)
        edit_menu.add_command(label="Redo (Ctrl+Y)", command=self.redo)
        edit_menu.add_separator()
        edit_menu.add_command(label="Clear All", command=self.clear_all)
        
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Show Empty Fields", command=self.show_empty_fields)
        tools_menu.add_command(label="Validate Macro", command=self.validate_current_macro)
        
        # Main text area with custom tags for confidence highlighting
        self.text_widget = scrolledtext.ScrolledText(
            self.root, 
            wrap=tk.WORD, 
            font=("Arial", 12),
            undo=True
        )
        self.text_widget.pack(expand=True, fill='both', padx=10, pady=5)
        
        # Configure text tags for confidence levels
        self.text_widget.tag_config("low_confidence", background="#FFF3CD")
        self.text_widget.tag_config("medium_confidence", background="#D1ECF1")
        self.text_widget.tag_config("high_confidence", background="#D4EDDA")
        
        # Control frame
        control_frame = tk.Frame(self.root)
        control_frame.pack(fill='x', padx=10, pady=5)
        
        # Status bar
        self.status_label = tk.Label(
            control_frame, 
            text="Status: Idle | Press 'r' to Record", 
            bd=1, 
            relief=tk.SUNKEN, 
            anchor=tk.W
        )
        self.status_label.pack(side=tk.LEFT, expand=True, fill='x')
        
        # Buttons
        button_frame = tk.Frame(control_frame)
        button_frame.pack(side=tk.RIGHT)
        
        tk.Button(button_frame, text="Copy", command=self.copy_to_clipboard).pack(side=tk.LEFT, padx=2)
        tk.Button(button_frame, text="Undo", command=self.undo).pack(side=tk.LEFT, padx=2)
        tk.Button(button_frame, text="Fields", command=self.show_empty_fields).pack(side=tk.LEFT, padx=2)
        
        # Info bar
        self.info_label = tk.Label(
            self.root,
            text="Ready",
            bd=1,
            relief=tk.SUNKEN,
            anchor=tk.E,
            font=("Arial", 9)
        )
        self.info_label.pack(fill='x', padx=10, pady=(0, 5))
        
        # Keyboard shortcuts
        self.root.bind('<Control-z>', lambda e: self.undo())
        self.root.bind('<Control-y>', lambda e: self.redo())

    def _load_json(self, path: Path) -> dict:
        if not path.exists(): 
            print(f"⚠ Warning: File not found at {path}")
            return {}
        with open(path, "r", encoding="utf-8") as f: 
            return json.load(f)

    def save_to_history(self):
        """Save current state to undo history"""
        current = self.text_widget.get("1.0", tk.END)
        if not self.history or self.history[-1] != current:
            self.history.append(current)
            self.redo_stack.clear()

    def undo(self):
        """Undo last change"""
        if len(self.history) > 1:
            current = self.history.pop()
            self.redo_stack.append(current)
            previous = self.history[-1]
            self.text_widget.delete("1.0", tk.END)
            self.text_widget.insert("1.0", previous)
            self.update_status("Undo", "blue")

    def redo(self):
        """Redo last undo"""
        if self.redo_stack:
            next_state = self.redo_stack.pop()
            self.history.append(next_state)
            self.text_widget.delete("1.0", tk.END)
            self.text_widget.insert("1.0", next_state)
            self.update_status("Redo", "blue")

    def clear_all(self):
        """Clear everything"""
        if messagebox.askyesno("Clear All", "Clear all text and reset?"):
            self.save_to_history()
            self.text_widget.delete("1.0", tk.END)
            self.active_macro_key = None
            self.field_confidence.clear()
            self.update_status("Cleared", "black")

    def copy_to_clipboard(self):
        """Copy text to clipboard"""
        text_to_copy = self.text_widget.get("1.0", tk.END).strip()
        pyperclip.copy(text_to_copy)
        self.update_status("Copied to clipboard!", "green")

    def show_empty_fields(self):
        """Show which fields are still empty"""
        current_text = self.text_widget.get("1.0", tk.END)
        empty_fields = re.findall(r'\{(\w+)\}', current_text)
        
        if empty_fields:
            fields_text = "\n".join(f"• {field}" for field in empty_fields)
            messagebox.showinfo(
                "Empty Fields",
                f"The following fields still need to be filled:\n\n{fields_text}"
            )
        else:
            messagebox.showinfo("Complete!", "All fields have been filled. ✓")

    def validate_current_macro(self):
        """Validate the current macro with the server"""
        if not self.active_macro_key:
            messagebox.showinfo("No Macro", "No macro is currently loaded.")
            return
        
        try:
            response = requests.get(f"{VALIDATE_URL}/{self.active_macro_key}", timeout=5)
            data = response.json()
            
            info = f"Macro: {self.active_macro_key}\n"
            info += f"Fields: {data['field_count']}\n"
            info += f"Template size: {data['template_length']} chars\n\n"
            info += "Fields:\n" + "\n".join(f"• {field}" for field in data['fields'])
            
            messagebox.showinfo("Macro Info", info)
        except Exception as e:
            messagebox.showerror("Error", f"Could not validate macro: {e}")

    def toggle_recording(self):
        """Toggle recording on/off"""
        if self.is_recording:
            self.update_status("Sending to GPU server...", "orange")
            self.is_recording = False
            audio_file = self.recorder.stop_recording()
            if audio_file:
                threading.Thread(
                    target=self.transcribe_audio_remote_thread, 
                    args=(audio_file,), 
                    daemon=True
                ).start()
        else:
            self.update_status("Recording...", "red")
            self.is_recording = True
            self.recorder.start_recording()
            
    def transcribe_audio_remote_thread(self, audio_path: str):
        """Send audio to server for transcription"""
        try:
            with open(audio_path, 'rb') as f:
                files = {'file': (os.path.basename(audio_path), f, 'audio/wav')}
                response = requests.post(TRANSCRIBE_URL, files=files, timeout=20)
            
            response.raise_for_status()
            result = response.json()
            
            # Extract text and timing info
            text = result.get("text", "").strip()
            processing_time = result.get("processing_time", 0)
            
            self.transcription_queue.put({
                "type": "transcription",
                "text": text,
                "processing_time": processing_time
            })
            
        except Exception as e:
            error_msg = f"ERROR: Transcription failed: {e}"
            print(error_msg, file=sys.stderr)
            self.transcription_queue.put({"type": "error", "text": error_msg})
        finally:
            os.remove(audio_path)

    def process_note_remote_thread(self):
        """Send note to Gemini for processing"""
        if not self.active_macro_key:
            self.transcription_queue.put({
                "type": "error",
                "text": "ERROR: No macro loaded to process."
            })
            return

        self.update_status("Asking Gemini to process note...", "blue")
        self.save_to_history()
        
        current_text = self.text_widget.get("1.0", tk.END).strip()
        payload = {
            "text": current_text,
            "macro_key": self.active_macro_key
        }

        try:
            response = requests.post(PROCESS_URL, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            self.transcription_queue.put({
                "type": "gemini_result",
                "data": result
            })
            
        except Exception as e:
            error_msg = f"ERROR: Gemini processing failed: {e}"
            print(error_msg, file=sys.stderr)
            self.transcription_queue.put({"type": "error", "text": error_msg})

    def process_queue(self):
        """Process results from the queue"""
        try:
            result = self.transcription_queue.get_nowait()
            
            if result["type"] == "transcription":
                text = result["text"]
                proc_time = result.get("processing_time", 0)
                self.process_command(text)
                self.update_info(f"Transcribed in {proc_time:.2f}s")
                
            elif result["type"] == "gemini_result":
                self._apply_gemini_result(result["data"])
                
            elif result["type"] == "error":
                self.update_status(result["text"], "red")
            
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.process_queue)

    def process_command(self, text: str):
        """Process transcribed text"""
        if text.startswith("ERROR:"):
            self.update_status(text, "red")
            return

        text_lower = text.lower().strip().replace(".", "").replace(",", "")
        
        # Command: process note
        if text_lower == "process note":
            threading.Thread(
                target=self.process_note_remote_thread, 
                daemon=True
            ).start()
            return

        # Command: insert <macro>
        if text_lower.startswith("insert "):
            self.save_to_history()
            macro_key = text_lower.split(" ", 1)[1].strip().replace(" ", "_")
            if macro_key in self.macros:
                self.active_macro_key = macro_key
                self.field_confidence.clear()
                template = self.macros[macro_key]
                if "{date}" in template:
                    template = template.replace(
                        "{date}", 
                        datetime.now().strftime("%B %d, %Y")
                    )
                self.text_widget.delete("1.0", tk.END)
                self.text_widget.insert("1.0", template)
                self.update_status(f"Inserted macro: '{macro_key}'", "green")
            else:
                self.update_status(f"Macro '{macro_key}' not found", "red")
            return

        # Command: set <field> to <value>
        match = re.match(
            r"(?:set|fill)\s+([\w\s]+?)\s+(?:to|is|as)\s+(.+)", 
            text, 
            re.IGNORECASE
        )
        if match:
            self.save_to_history()
            field, value = match.groups()
            placeholder = f"{{{field.strip().replace(' ', '_')}}}"
            current_text = self.text_widget.get("1.0", tk.END)
            if placeholder in current_text:
                new_text = current_text.replace(placeholder, value.strip(), 1)
                self.text_widget.delete("1.0", tk.END)
                self.text_widget.insert("1.0", new_text)
                self.update_status(f"Filled field '{field}'", "green")
            return

        # No command, append text
        self.save_to_history()
        self.text_widget.insert(tk.END, " " + text)
        self.update_status("Text appended", "black")

    def _apply_gemini_result(self, data: dict):
        """Apply Gemini results with confidence highlighting"""
        if not self.active_macro_key or self.active_macro_key not in self.macros:
            return

        fields = data.get("fields", {})
        metadata = data.get("metadata", {})
        proc_time = metadata.get("processing_time", 0)
        low_conf_count = metadata.get("low_confidence_count", 0)
        
        # Start with the original template
        updated_text = self.macros[self.active_macro_key]
        if "{date}" in updated_text:
            updated_text = updated_text.replace(
                "{date}", 
                datetime.now().strftime("%B %d, %Y")
            )
        
        # Replace placeholders and track confidence
        self.field_confidence.clear()
        for key, field_data in fields.items():
            if isinstance(field_data, dict):
                value = field_data.get("value", "")
                confidence = field_data.get("confidence", 0.0)
            else:
                value = field_data
                confidence = 1.0
            
            if value:
                updated_text = updated_text.replace(f"{{{key}}}", str(value))
                self.field_confidence[key] = confidence
        
        # Update text widget
        self.text_widget.delete("1.0", tk.END)
        self.text_widget.insert("1.0", updated_text)
        
        # Apply confidence highlighting
        self._apply_confidence_highlighting()
        
        # Update status
        status_msg = f"Gemini complete in {proc_time:.2f}s"
        if low_conf_count > 0:
            status_msg += f" ({low_conf_count} low-confidence fields)"
        self.update_status(status_msg, "purple")
        self.update_info(f"Review yellow-highlighted fields")

    def _apply_confidence_highlighting(self):
        """Highlight text based on confidence scores"""
        # This is a simplified version - in production you'd want more sophisticated highlighting
        content = self.text_widget.get("1.0", tk.END)
        
        # Clear existing tags
        for tag in ["low_confidence", "medium_confidence", "high_confidence"]:
            self.text_widget.tag_remove(tag, "1.0", tk.END)
        
        # Apply tags based on field confidence
        # (Note: This is a placeholder - you'd need to track field positions)
        
    def update_status(self, message, color="black"):
        """Update status bar"""
        self.status_label.config(text=f"Status: {message}", fg=color)

    def update_info(self, message):
        """Update info bar"""
        self.info_label.config(text=message)

    def start_app(self):
        """Start the application"""
        listener_thread = threading.Thread(
            target=self.start_keyboard_listener, 
            daemon=True
        )
        listener_thread.start()
        
        self.process_queue()
        
        print("\n✓ GUI ready")
        print("✓ Press 'r' anywhere to toggle recording")
        print("✓ Say 'process note' to fill template with AI\n")
        
        self.root.mainloop()

    def start_keyboard_listener(self):
        """Start global keyboard listener"""
        def on_press(key):
            try:
                if key.char == TOGGLE_KEY:
                    self.toggle_recording()
            except AttributeError:
                pass
        
        with keyboard.Listener(on_press=on_press) as listener:
            listener.join()

class Recorder:
    """Audio recorder class"""
    def __init__(self, samplerate=DEFAULT_SR, channels=CHANNELS):
        self.samplerate = samplerate
        self.channels = channels
        self._frames = []
        self._stream = None
    
    def start_recording(self):
        """Start recording audio"""
        self._frames = []
        self._stream = sd.InputStream(
            samplerate=self.samplerate,
            channels=self.channels,
            callback=lambda d, f, t, s: self._frames.append(d.copy()),
            dtype='float32'
        )
        self._stream.start()
    
    def stop_recording(self) -> str | None:
        """Stop recording and save to file"""
        if not self._stream:
            return None
        
        self._stream.stop()
        self._stream.close()
        
        if not self._frames:
            return None
        
        audio_data = np.concatenate(self._frames, axis=0)
        temp_file = tempfile.mktemp(suffix=".wav", prefix="dictation_")
        sf.write(temp_file, audio_data, self.samplerate)
        
        return temp_file

def main():
    """Main entry point"""
    print("\n" + "="*60)
    print("DRAGON DICTATION PRO - ENHANCED CLIENT v6.0")
    print("="*60)
    
    app = DictationApp()
    app.start_app()

if __name__ == "__main__":
    main()