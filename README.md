# Dragon Dictation Pro - Enhanced Edition

A production-grade, AI-powered medical dictation system with intelligent entity extraction and confidence scoring.

## 🆕 What's New in v6.0

### Client Enhancements
- **📊 Confidence Score Highlighting**: Low-confidence fields automatically highlighted in yellow for review
- **⏱️ Performance Metrics**: Real-time processing time display
- **🔄 Full Undo/Redo**: Complete history tracking with 50-level undo buffer
- **🎯 Field Validation**: Quick view of empty fields and macro structure
- **⌨️ Keyboard Shortcuts**: Ctrl+Z (undo), Ctrl+Y (redo)
- **📋 Enhanced Status Bar**: Detailed feedback on all operations
- **🏥 Health Check**: Automatic server connectivity verification on startup

### Server Enhancements
- **🎯 Confidence Scoring**: Every field extraction includes confidence (0.0-1.0)
- **🔄 Automatic Fallback**: Regex-based extraction when Gemini fails
- **📊 Performance Monitoring**: Detailed timing logs for all operations
- **🛡️ Better Error Handling**: Comprehensive logging and graceful degradation
- **✅ Macro Validation Endpoint**: Validate templates before use
- **📋 Macro Listing Endpoint**: Browse available templates
- **🏥 Enhanced Health Check**: Detailed status information

## 🏗️ Architecture

```
┌─────────────────┐         Tailscale VPN         ┌──────────────────┐
│  Work Laptop    │◄──────────────────────────────►│  Home Server     │
│                 │      Encrypted Mesh Network    │                  │
│  Tkinter GUI    │                                │  Docker Container│
│  - Audio Input  │                                │  - Flask API     │
│  - Text Display │                                │  - Whisper (GPU) │
│  - Confidence   │                                │  - Gemini API    │
│    Highlighting │                                │  - RTX 3090      │
└─────────────────┘                                └──────────────────┘
```

## 🔑 Key Features

### Two-Tier AI System
1. **Whisper (faster-whisper)**: GPU-accelerated speech-to-text
2. **Gemini 1.5 Flash**: Intelligent entity extraction and template filling

### Confidence-Aware Scribing
- **High Confidence (0.8-1.0)**: Green highlight - Good to go
- **Medium Confidence (0.6-0.8)**: Blue highlight - Worth reviewing
- **Low Confidence (0.0-0.6)**: Yellow highlight - Needs attention

### Smart Workflows

#### Workflow A: Manual Template Filling (Precise)
```
1. Say: "insert carotid ultrasound"
   → Template loads with placeholders

2. Say: "set indication to stroke follow up"
   → {indication} filled with your exact words

3. Say: "set findings to sixty percent stenosis"
   → {findings} filled

4. Copy to EMR
```

#### Workflow B: AI Scribing (Fast)
```
1. Say: "insert carotid ultrasound"
   → Template loads

2. Dictate naturally:
   "The indication for this exam is stroke follow-up.
    The right internal carotid shows moderate plaque 
    with sixty percent stenosis. Left ICA is patent.
    Impression is moderate right ICA stenosis."

3. Say: "process note"
   → Gemini extracts entities and fills ALL fields
   → Low-confidence fields highlighted in yellow

4. Review highlighted fields, make corrections

5. Copy to EMR
```

## 📦 Installation

### Backend Server Setup

1. **Prepare Server** (Ubuntu/Debian with NVIDIA GPU)
```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

2. **Create Project Structure**
```bash
mkdir -p dragon_server/config
cd dragon_server
```

3. **Create Dockerfile**
```dockerfile
FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
RUN pip install --no-cache-dir \
    flask \
    waitress \
    faster-whisper \
    google-generativeai

# Copy application files
COPY server.py /app/
COPY config/ /app/config/

EXPOSE 5005

CMD ["python", "server.py"]
```

4. **Build and Run**
```bash
# Build image
sudo docker build -t dragon-server .

# Run container
sudo docker run -d \
  --name dragon-server \
  --gpus all \
  -p 5005:5005 \
  -e GOOGLE_API_KEY="your-api-key-here" \
  -v $(pwd)/config:/app/config \
  --restart unless-stopped \
  dragon-server

# Check logs
sudo docker logs -f dragon-server
```

### Client Setup

1. **Install Python Dependencies**
```bash
conda create -n dragon_client python=3.10 -y
conda activate dragon_client
pip install numpy sounddevice soundfile pynput pyperclip requests tkinter
```

2. **Configure Server URL**
Edit `dragon_mvp.py` and set your server IP:
```python
SERVER_BASE_URL = "http://YOUR_SERVER_IP:5005"
```

3. **Run Client**
```bash
python dragon_mvp.py
```

## 🎮 Usage Guide

### Voice Commands

| Command | Action |
|---------|--------|
| `insert <macro_name>` | Load template (e.g., "insert bilateral arteriogram") |
| `set <field> to <value>` | Fill specific field manually |
| `process note` | **AI magic**: Gemini fills ALL fields from your dictation |
| *(any natural speech)* | Appends text to current note |

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `r` (anywhere) | Toggle recording on/off |
| `Ctrl+Z` | Undo last change |
| `Ctrl+Y` | Redo |
| `Ctrl+C` | Copy (standard) |

### GUI Buttons

- **Copy**: Copy entire note to clipboard
- **Undo**: Step back through history
- **Fields**: Show which placeholders are still empty

### Menu Options

**Edit Menu**:
- Undo (Ctrl+Z)
- Redo (Ctrl+Y)
- Clear All

**Tools Menu**:
- Show Empty Fields
- Validate Macro

## 🔧 API Reference

### Server Endpoints

#### `GET /`
Health check with system info
```json
{
  "status": "healthy",
  "whisper_model": "medium.en",
  "device": "cuda",
  "gemini_enabled": true,
  "macros_loaded": 15
}
```

#### `POST /transcribe`
Transcribe audio file
- **Input**: WAV file (multipart/form-data)
- **Output**:
```json
{
  "text": "transcribed text",
  "segments": [{"text": "...", "start": 0.0, "end": 2.5}],
  "language": "en",
  "duration": 2.5,
  "processing_time": 0.87
}
```

#### `POST /process_note`
Process note with Gemini
- **Input**:
```json
{
  "text": "dictated text with findings",
  "macro_key": "carotid_ultrasound"
}
```
- **Output**:
```json
{
  "fields": {
    "indication": {
      "value": "stroke follow-up",
      "confidence": 0.95
    },
    "findings": {
      "value": "60% stenosis right ICA",
      "confidence": 0.85
    }
  },
  "metadata": {
    "processing_time": 2.3,
    "macro_key": "carotid_ultrasound",
    "low_confidence_count": 1
  }
}
```

#### `GET /validate_macro/<macro_key>`
Validate macro structure
```json
{
  "macro_key": "bilateral_arteriogram",
  "fields": ["indication", "technique", "findings", "impression"],
  "field_count": 4,
  "template_length": 512
}
```

#### `GET /list_macros`
List all available macros
```json
{
  "macros": ["carotid_ultrasound", "bilateral_arteriogram", ...],
  "count": 15
}
```

## 🐛 Troubleshooting

### Check Server Logs
```bash
sudo docker logs -f dragon-server
```

### Common Issues

**"Gemini processing failed"**
- Check API key: `sudo docker exec dragon-server printenv GOOGLE_API_KEY`
- Check logs for rate limiting or quota issues
- Verify internet connectivity from server

**"Connection refused"**
- Verify server is running: `sudo docker ps`
- Check Tailscale connection: `tailscale status`
- Verify firewall allows port 5005

**"Low audio quality"**
- Check microphone in system settings
- Test with: `python -c "import sounddevice as sd; print(sd.query_devices())"`
- Try different `--mic-index` value

**"Fields not highlighting"**
- Confidence highlighting requires server v2.0+
- Check server version in health check endpoint

### Performance Optimization

**Slow Transcription**
- Ensure GPU is being used: Check "device": "cuda" in health check
- Monitor GPU usage: `nvidia-smi -l 1`
- Try smaller model: `medium.en` → `small.en`

**Slow Gemini Processing**
- Normal: 2-5 seconds for complex templates
- Check quota: https://aistudio.google.com/app/apikey
- Consider caching common extractions

## 📊 Performance Benchmarks

Measured on RTX 3090 + Ryzen 9 5950X:

| Operation | Time | Notes |
|-----------|------|-------|
| Transcription (10s audio) | 0.8-1.2s | Medium.en model |
| Gemini Processing | 2-4s | Depends on template complexity |
| Round-trip Latency | 3-6s | Record → filled template |

## 🔒 Security Notes

- ✅ All transcription happens locally (HIPAA-friendly)
- ✅ Gemini API uses TLS encryption
- ✅ Tailscale provides zero-trust mesh VPN
- ✅ No patient data stored on servers
- ⚠️ Gemini API receives dictated text (consider your compliance requirements)

## 🗺️ Roadmap

- [ ] Structured output mode for Gemini (more reliable JSON)
- [ ] Streaming transcription for live feedback
- [ ] Multi-user support with authentication
- [ ] Voice commands for field navigation
- [ ] Export to FHIR format
- [ ] Integration with Epic/Cerner APIs
- [ ] Offline Gemini alternative (local LLM)
- [ ] Mobile app (iOS/Android)

## 📄 License

MIT License - See LICENSE file

## 🙏 Acknowledgments

- faster-whisper by Guillaume Klein
- Google Gemini API
- Anthropic Claude for development assistance

---

**Made with ❤️ for physicians who value their time**