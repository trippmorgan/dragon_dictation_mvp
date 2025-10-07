
## Voice Command Reference

| Command                   | Action                                                                   |
| ------------------------- | ------------------------------------------------------------------------ |
| `insert <macro_name>`     | Loads a template from `macros.json` into the buffer.                     |
| `set <field> to <value>`  | Fills a placeholder (e.g., `{field}`) with the specified value.          |
| `fill <field> <value>`    | Alternative syntax for filling a placeholder.                            |
| `paste buffer`            | Pastes the current buffer contents into the active window.               |
| `scratch that`            | Deletes the last spoken phrase from the buffer.                          |
| `clear buffer`            | Empties the buffer and clears the active macro.                          |
| `undo paste`              | Simulates a `Ctrl+Z`/`Cmd+Z` to undo the last paste.                     |
| `show fields`             | Displays a list of any remaining unfilled `{placeholders}` in the buffer. |
| `newline` / `new paragraph` | Inserts line breaks.                                                     |
| `period` / `comma` / etc. | Inserts punctuation.                                                     |

---
# Dragon-like Dictation Pro (GUI Edition)

A local, private, and intelligent medical dictation assistant designed to streamline clinical documentation. This application provides a dedicated graphical user interface (GUI) for dictating, editing, and managing structured medical reports. It uses `faster-whisper` for high-accuracy, offline speech recognition and features a powerful macro and slot-filling system based on your own templates.

 <!-- Generic placeholder screenshot -->

## ✨ Core Features

-   **🖥️ Dedicated GUI:** A clean, persistent window serves as a "staging area" for your dictations. No more terminal clutter.
-   **⏯️ Toggle-to-Record:** Simply press the **`r`** key anywhere on your system to start or stop recording. No need to hold down a key.
-   **🔑 Smart Macros:** Say **`insert <procedure>`** (e.g., `insert shuntogram`) to instantly load a complete, structured report template from `config/macros.json`.
-   **🧩 Voice Slot-Filling:** After loading a macro, fill placeholders by saying **`set <field> to <value>`** (e.g., `set artery to superficial femoral`).
-   **📋 One-Click Copy:** A "Copy to Clipboard" button lets you easily transfer your finalized note to your EMR or any other application.
-   **🎨 Live Status Bar:** The GUI provides real-time feedback on the app's status: `Idle`, `Recording...`, or `Transcribing...`.
-   **🔒 100% Local & Private:** All audio processing and transcription happens on your machine. No data is ever sent to the cloud, ensuring patient privacy.

## 📂 Project Structure

```
dragon_dictation_mvp/
├── dragon_mvp.py            # The main application script (GUI Edition)
├── requirements.txt         # Python dependencies
├── README.md                # This file
│
├── config/
│   ├── hotwords.txt         # Your custom medical vocabulary (for ASR boosting)
│   └── macros.json          # Your procedure templates
│
└── data/
    └── logs/                # (Future) Session logs
```

## 🛠️ Setup (with Conda)

1.  **Create Conda Environment:**
    If you haven't already, create a dedicated environment.
    ```bash
    conda create -n dragon_dictation python=3.10 -y
    conda activate dragon_dictation
    ```

2.  **Install PyTorch:**
    Choose the command that matches your hardware.
    ```bash
    # For CPU-only systems (including Apple Silicon Macs)
    conda install pytorch torchvision torchaudio cpuonly -c pytorch -y

    # For NVIDIA GPUs (CUDA 12.1 example)
    conda install pytorch torchvision torchaudio pytorch-cuda=12.1 -c pytorch -c nvidia -y
    ```

3.  **Install App Dependencies:**
    Navigate to the project folder and run:
    ```bash
    pip install -r requirements.txt
    ```
    *Note: On some Linux systems, you may need to install the Tkinter library if it's not included with Python: `sudo apt-get install python3-tk`.*


## ▶️ How to Run

1.  Navigate to the project directory in your terminal.
2.  Run the script:
    ```bash
    python dragon_mvp.py --model small.en
    ```
3.  A GUI window titled "Medical Dictation Assistant" will appear. You can minimize your terminal.

##  workflow in action

1.  The GUI window is open. You can work in any other application (EMR, web browser, etc.).
2.  Press the **`r`** key to start recording. The status bar will turn red.
3.  Dictate your command or text. For example: `insert bilateral arteriogram`.
4.  Press **`r`** again to stop. The status bar will turn orange (`Transcribing...`) and then the template will appear in the GUI window.
5.  Press **`r`**, dictate `set indication to rest pain`, and press **`r`** again. The `{indication}` placeholder in the window will be filled.
6.  Continue this process until the note is complete.
7.  Click the **"Copy to Clipboard"** button in the GUI.
8.  Click into your EMR and paste (`Cmd+V` or `Ctrl+V`).

## Voice Command Reference

| Command                   | Action                                                                   |
| ------------------------- | ------------------------------------------------------------------------ |
| `insert <macro_name>`     | Clears the window and loads a template from `macros.json`.               |
| `set <field> to <value>`  | Finds the placeholder `{field}` and replaces it with the dictated value. |
| `(any other text)`        | Appends the dictated text to the end of the current note.                |

---