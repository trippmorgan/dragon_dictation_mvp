# Dragon-like Dictation Pro

A local, private, and intelligent medical dictation assistant designed to streamline clinical documentation. This app uses `faster-whisper` for high-accuracy speech recognition and features a powerful macro and slot-filling system inspired by your own dictation templates.

## ✨ Pro Features

-   **🎙️ Push-to-Talk:** Hold **F9** to dictate, release to process.
-   **🔑 Smart Macros:** Say **`insert <procedure>`** (e.g., `insert shuntogram`) to load a complete, structured report template from `config/macros.json`.
-   **🧩 Voice Slot-Filling:** After loading a macro, fill placeholders by saying **`set <field> to <value>`** (e.g., `set artery to superficial femoral`).
-   **🧠 Contextual ASR:** The speech recognition engine is automatically primed with your custom medical terms (`hotwords.txt`) and keywords from the active macro for superior accuracy.
-   **📋 Intelligent Buffer:** Your dictation builds up in a buffer. You have full voice control over editing and pasting.
-   **✍️ Voice Commands:**
    -   **Pasting:** `paste buffer`, `undo paste`
    -   **Editing:** `scratch that` (removes last phrase), `clear buffer`
    -   **Formatting:** `newline`, `new paragraph`, `period`, `comma`
    -   **Utility:** `show fields` (lists remaining placeholders)
-   **🔒 100% Local:** All audio processing happens on your machine. No data is sent to the cloud.
-   **🗂️ Session Logging:** Transcripts and actions are automatically logged to the `data/logs/` directory for review.

## 📂 Project Structure

```
dragon_dictation_mvp/
├── dragon_mvp.py            # The main application script
├── requirements.txt         # Python dependencies
├── README.md                # This file
│
├── config/
│   ├── hotwords.txt         # Your custom medical vocabulary
│   └── macros.json          # Your procedure templates
│
├── data/
│   ├── corrections/         # (Future) For storing corrected text to fine-tune the model
│   └── logs/                # Automatically created session logs
│
└── models/                  # (Future) For custom-trained model adapters
```

## 🛠️ Setup (with Conda)

1.  **Create Conda Environment:**
    ```bash
    conda create -n dragon_dictation python=3.10 -y
    conda activate dragon_dictation
    ```

2.  **Install PyTorch:**
    Choose the command that matches your hardware.
    ```bash
    # For CPU-only systems
    conda install pytorch torchvision torchaudio cpuonly -c pytorch -y

    # For NVIDIA GPUs (CUDA 12.1 example)
    conda install pytorch torchvision torchaudio pytorch-cuda=12.1 -c pytorch -c nvidia -y
    ```

3.  **Install App Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## ▶️ How to Run

Navigate to the project directory and run the script:

```bash
cd dragon_dictation_mvp
python dragon_mvp.py --model small.en
```

## Workflow Example

1.  Click into your EMR or text editor.
2.  **Hold F9** and say: `insert bilateral arteriogram`. Release F9.
    -   The terminal will show the macro loaded into the buffer and list the remaining fields (`{indication}`, `{artery}`, etc.).
3.  **Hold F9** and say: `set indication to rest pain`. Release F9.
    -   The terminal shows the `{indication}` field has been filled.
4.  **Hold F9** and say: `set narrative to The patient was brought to the operating room and placed in the supine position period new paragraph Access was obtained in the right common femoral artery period`. Release F9.
5.  Continue filling fields until `show fields` reports none are left.
6.  **Hold F9** and say: `paste buffer`. Release F9.
    -   The complete, formatted note is pasted into your EMR.

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