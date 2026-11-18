"""Задачи для разметки реплик на временной оси в Label Studio.

Одна задача — один разговор: две синхронные дорожки 16 кГц, по одной на каждого спикера.
На волну заранее ставятся отрезки речи (предразметка): слова с временными метками из файлов источника,
между которыми меньше MIN_PAUSE_S, склеиваются в один отрезок. Аннотатор склеивает отрезки в реплики,
и каждая пауза от MIN_PAUSE_S между отрезками одного спикера либо остаётся границей реплики (конец реплики),
либо оказывается внутри реплики.

В данных задачи — список этих пауз (pauses): по нему потом считается согласие аннотаторов.

Запуск: python scripts/make_turn_tasks.py
Читает data/manual_audio/conversations.csv и raw/, пишет turns_audio/ и tasks_turns.json.
"""

import csv
import json
from math import gcd
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly

ROOT = Path(__file__).resolve().parent.parent / "data" / "manual_audio"
RAW, OUT = ROOT / "raw", ROOT / "turns_audio"
MIN_PAUSE_S = 0.2
OUT_SR = 16000
LABELS = {"1": "Реплика спикера 1", "2": "Реплика спикера 2"}


def load(track_id):
    sr, x = wavfile.read(RAW / f"{track_id}.wav")
    x = x.astype(np.float32)
    return sr, x.mean(axis=1) if x.ndim > 1 else x


def speech_segments(track_id):
    words = sorted((w["start"], w["end"])
                   for line in open(RAW / f"{track_id}.transcript.jsonl", encoding="utf-8") if line.strip()
                   for w in json.loads(line).get("words", [])
                   if w.get("start") is not None and w.get("end") is not None)
    merged = []
    for start, end in words:
        if merged and start - merged[-1][1] < MIN_PAUSE_S:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def region(rid, speaker, start, end):
    return {"id": rid, "from_name": f"turn{speaker}", "to_name": f"audio{speaker}", "type": "labels",
            "origin": "prediction",
            "value": {"start": round(start, 3), "end": round(end, 3), "labels": [LABELS[speaker]]}}


def main():
    OUT.mkdir(exist_ok=True)
    tasks = []
    for conv in csv.DictReader(open(ROOT / "conversations.csv", encoding="utf-8", newline="")):
        cid = conv["conversation_id"]
        tracks = {"1": conv["speaker_1_file"], "2": conv["speaker_2_file"]}
        segs = {s: speech_segments(t) for s, t in tracks.items()}
        if not all(segs.values()):
            print(f"{cid}: нет расшифровки, пропущен")
            continue
        audio = {s: load(t) for s, t in tracks.items()}
        sr = audio["1"][0]
        n = min(len(x) for _, x in audio.values())
        g = gcd(OUT_SR, sr)
        for s, (_, x) in audio.items():
            y = resample_poly(x[:n], OUT_SR // g, sr // g)
            wavfile.write(OUT / f"{cid}_s{s}.wav", OUT_SR, (np.clip(y, -1, 1) * 32767).astype(np.int16))

        pauses, result = [], []
        for s in ("1", "2"):
            for i, (st, en) in enumerate(segs[s]):
                result.append(region(f"{cid}_s{s}_r{i + 1:03d}", s, st, en))
            for k, ((_, p0), (p1, _)) in enumerate(zip(segs[s], segs[s][1:]), 1):
                pauses.append({"pause_id": f"{cid}_s{s}_p{k:03d}", "speaker": s,
                               "start": round(p0, 3), "end": round(p1, 3)})
        tasks.append({
            "data": {"audio1": f"/data/local-files/?d=turns_audio/{cid}_s1.wav",
                     "audio2": f"/data/local-files/?d=turns_audio/{cid}_s2.wav", "conversation_id": cid,
                     "duration_s": round(n / sr, 1), "pauses": pauses},
            "predictions": [{"model_version": "speech_segments", "result": result}],
        })
        print(f"{cid}: пауз {len(pauses)}")
    with open(ROOT / "tasks_turns.json", "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=1)
    print(f"разговоров: {len(tasks)}, пауз: {sum(len(t['data']['pauses']) for t in tasks)}")


if __name__ == "__main__":
    main()
