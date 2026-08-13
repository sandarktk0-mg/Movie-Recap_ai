# Movie Recap AI – Final V1

## What it does

1. Upload a movie/video from phone or PC.
2. FFmpeg extracts audio.
3. OpenAI transcription converts dialogue/audio to text.
4. OpenAI text model creates a Burmese recap narration.
5. OpenAI TTS generates narration audio.
6. Burmese subtitles are generated from the narration.
7. FFmpeg creates a final MP4 with the original video muted + Burmese narration + subtitles.

## Requirements

- Python 3.10+
- FFmpeg installed and available in PATH
- An OpenAI API key

## Setup

### Windows / macOS / Linux

    python -m venv .venv
    # Windows:
    .venv\Scripts\activate
    # macOS/Linux:
    source .venv/bin/activate

    pip install -r requirements.txt

Copy `.env.example` to `.env` and put your API key in:

    OPENAI_API_KEY=...

Then:

    python app.py

Open:

    http://127.0.0.1:5000

## Phone use

For a real phone-only experience, deploy this project to a server/cloud host that has:
- Python
- FFmpeg
- enough disk space
- HTTPS
- your API key stored as a server environment variable

Then open the deployed URL in Chrome on Android.

Do NOT put the API key into the frontend JavaScript.

## Important limitations

This V1 analyzes the movie primarily through extracted audio/transcription. It does not fully understand silent visual events. A stronger V2 can add sampled video frames/vision analysis and scene selection.

Large movies can take a long time and cost more API/compute resources. For testing, use a short clip first.

Copyright: only process videos you own or have permission to use. If you publish recap videos using movie footage, check the copyright rules that apply to your jurisdiction/platform.
