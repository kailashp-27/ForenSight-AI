import os, sys, glob, warnings
from pathlib import Path

warnings.filterwarnings('ignore')

# Inject ffmpeg
LOCALAPPDATA = os.environ.get('LOCALAPPDATA', '')
ffmpeg_path = Path(LOCALAPPDATA) / 'Microsoft' / 'WinGet' / 'Packages' / 'Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe' / 'ffmpeg-9.0.1-full_build' / 'bin'
if ffmpeg_path.exists():
    os.environ['PATH'] = str(ffmpeg_path) + os.pathsep + os.environ.get('PATH', '')
    print(f'ffmpeg injected from: {ffmpeg_path}')
else:
    print(f'ffmpeg NOT found at: {ffmpeg_path}')
    sys.exit(1)

import whisper
print('Loading Whisper base model...')
model = whisper.load_model('base')
print('Model loaded.')

files = (
    glob.glob(r'backend\storage\**\*.mp3', recursive=True) + 
    glob.glob(r'backend\storage\**\*.wav', recursive=True)
)
if not files:
    print('No audio files found in backend/storage')
    sys.exit(1)

audio_file = files[0]
print(f'Transcribing: {audio_file}')
result = model.transcribe(audio_file, verbose=False)

segs = result.get('segments', [])
lang = result.get('language', 'unknown')
text = result.get('text', '').strip()
print(f'SUCCESS - Language: {lang}, Segments: {len(segs)}, Words: {len(text.split())}')
print(f'Full transcript preview: {text[:300]}')
print()
for s in segs[:6]:
    print(f'  [{s["start"]:.1f}s - {s["end"]:.1f}s] {s["text"].strip()}')
