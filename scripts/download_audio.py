"""Скачивает аудио собранных разговоров по описи data/manual_audio/conversations.csv.

На каждую дорожку три файла из открытого источника (Seamless Interaction, часть naturalistic/dev):
<id>.wav, <id>.vad.jsonl, <id>.transcript.jsonl — в data/manual_audio/raw/. Около 400 МБ.
Уже скачанные файлы пропускаются.

Запуск: python scripts/download_audio.py
"""

import csv
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "data" / "manual_audio"
RAW = ROOT / "raw"
BASE = "https://dl.fbaipublicfiles.com/seamless_interaction/naturalistic/dev"
FILES = {"audio/{id}.wav": "{id}.wav",
         "metadata/vad/{id}.jsonl": "{id}.vad.jsonl",
         "metadata/transcript/{id}.jsonl": "{id}.transcript.jsonl"}


def main():
    RAW.mkdir(exist_ok=True)
    for conv in csv.DictReader(open(ROOT / "conversations.csv", encoding="utf-8", newline="")):
        for track in (conv["speaker_1_file"], conv["speaker_2_file"]):
            for remote, local in FILES.items():
                path = RAW / local.format(id=track)
                if path.exists():
                    continue
                urllib.request.urlretrieve(f"{BASE}/{remote.format(id=track)}", path)
                print(f"{conv['conversation_id']}: {path.name}")
    print("готово")


if __name__ == "__main__":
    main()
