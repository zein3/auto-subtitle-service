# Auto Subtitle Service

Created with FastAPI, ffmpeg, and whisper.cpp

### How to Run

1. Get [whisper.cpp](https://github.com/ggml-org/whisper.cpp) and [ffmpeg](https://github.com/FFmpeg/FFmpeg)

2. Install required libraries

```bash
pip install -r requirements.txt
```

3. Copy the env file, and edit it

```bash
cp .env.local .env
nvim .env
```

4. Run the service

```bash
fastapi dev main.py
```

or

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
