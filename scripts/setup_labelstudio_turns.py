"""Создаёт в Label Studio проект разметки реплик на временной оси и загружает разговоры из tasks_turns.json.

Нужно: запущенный Label Studio с переменными окружения
  LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED=true
  LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT=<путь к data/manual_audio>
и токен доступа пользователя (Account & Settings → Legacy Token) в переменной LS_TOKEN.

Запуск: python scripts/setup_labelstudio_turns.py [адрес, по умолчанию http://localhost:8080]
"""

import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "data" / "manual_audio"
URL = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080").rstrip("/")
TOKEN = os.environ["LS_TOKEN"]

LABEL_CONFIG = """
<View>
  <Header value="Разговор $conversation_id" size="5"/>
  <Header value="Спикер 1" size="6"/>
  <Labels name="turn1" toName="audio1">
    <Label value="Реплика спикера 1" background="#4C78A8"/>
  </Labels>
  <Audio name="audio1" value="$audio1" sync="audio2" hotkey="space"/>
  <Header value="Спикер 2" size="6"/>
  <Labels name="turn2" toName="audio2">
    <Label value="Реплика спикера 2" background="#F58518"/>
  </Labels>
  <Audio name="audio2" value="$audio2" sync="audio1"/>
</View>
"""

INSTRUCTION = """
<p>Задача — разбить речь каждого спикера на реплики. Дорожки спикеров воспроизводятся синхронно. На волне уже стоят отрезки речи; между ними — паузы.</p>
<ul>
<li>Если пауза внутри реплики (спикер подбирает слова, переводит дыхание и продолжает) — растяните отрезок
до конца реплики и удалите лишние отрезки, чтобы реплика стала одним отрезком.</li>
<li>Если перед паузой реплика закончилась и слово перешло к собеседнику — оставьте здесь границу.</li>
</ul>
<p>Конец каждого отрезка — конец реплики. Поддакивания собеседника («угу», «yeah») не делают паузу концом реплики.</p>
<p>Подробные правила и спорные случаи — в codebook (docs/codebook_eot.md). Метки напарника не смотрите.</p>
"""


def api(method, path, body=None):
    req = urllib.request.Request(
        f"{URL}{path}", method=method,
        data=json.dumps(body).encode("utf-8") if body is not None else None,
        headers={"Authorization": f"Token {TOKEN}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read() or b"{}")


def main():
    project = api("POST", "/api/projects", {
        "title": "TurnBench: реплики",
        "description": "Разметка реплик в собранных разговорах: где заканчивается каждая реплика.",
        "label_config": LABEL_CONFIG,
        "expert_instruction": INSTRUCTION,
        "show_instruction": True,
        "maximum_annotations": 2,
        "show_collab_predictions": True,
    })
    pid = project["id"]
    api("POST", "/api/storages/localfiles", {
        "project": pid, "title": "Разговоры",
        "path": str(ROOT / "turns_audio"), "use_blob_urls": False,
    })
    tasks = json.load(open(ROOT / "tasks_turns.json", encoding="utf-8"))
    result = api("POST", f"/api/projects/{pid}/import", tasks)
    print(f"проект {pid}: загружено задач {result.get('task_count', len(tasks))}")
    print(f"{URL}/projects/{pid}/data")


if __name__ == "__main__":
    main()
