"""Поднимает в своём Label Studio оба проекта разметки вместе с уже сделанной разметкой.

Берёт выгрузки из data/annotations/ (spml_labelstudio.json, turns_labelstudio.json), создаёт проекты
с теми же настройками, что setup_labelstudio_spml.py и setup_labelstudio_turns.py, и загружает задачи
с аннотациями. Автор каждой аннотации восстанавливается по почте: в выгрузке аннотатор записан номером,
номер сопоставляется с почтой учётной записи в вашем Label Studio через параметр --annotator.
Учётные записи для обоих аннотаторов должны быть заведены заранее (Organization → участники),
иначе аннотация достанется тому, кто запускает импорт.

Нужно: запущенный Label Studio с раздачей локальных файлов (см. README), подготовленные дорожки
(scripts/download_audio.py, scripts/make_turn_tasks.py) и токен доступа в переменной LS_TOKEN.

Запуск:
  python scripts/import_labelstudio.py --annotator 1=<почта Егора> --annotator 4=<почта Антона>
  [--url http://localhost:8080]
"""

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import setup_labelstudio_spml as spml  # noqa: E402
import setup_labelstudio_turns as turns  # noqa: E402

PROJECTS = [
    {"export": "spml_labelstudio.json", "title": "SPML: атака или нет", "setup": spml,
     "description": "Разметка собранных пользовательских промптов: безопасный запрос или атака на бота.",
     "extra": {"sampling": "Uniform sampling"}, "storage": None},
    {"export": "turns_labelstudio.json", "title": "TurnBench: реплики", "setup": turns,
     "description": "Разметка реплик в собранных разговорах: где заканчивается каждая реплика.",
     "extra": {"show_collab_predictions": True}, "storage": ROOT / "data" / "manual_audio" / "turns_audio"},
]


def api(url, token, method, path, body=None):
    req = urllib.request.Request(
        f"{url}{path}", method=method,
        data=json.dumps(body).encode("utf-8") if body is not None else None,
        headers={"Authorization": f"Token {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read() or b"{}")


def to_import(task, emails):
    anns = []
    for a in task["annotations"]:
        if a.get("was_cancelled"):
            continue
        ann = {"result": a["result"], "lead_time": a.get("lead_time"), "was_cancelled": False,
               "ground_truth": a.get("ground_truth", False)}
        if a["completed_by"] in emails:
            ann["completed_by"] = {"email": emails[a["completed_by"]]}
        anns.append(ann)
    return {"data": task["data"], "annotations": anns}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--annotator", action="append", default=[], metavar="НОМЕР=ПОЧТА")
    ap.add_argument("--url", default="http://localhost:8080")
    args = ap.parse_args()
    emails = {int(k): v for k, v in (x.split("=", 1) for x in args.annotator)}
    url, token = args.url.rstrip("/"), os.environ["LS_TOKEN"]

    for p in PROJECTS:
        tasks = json.load(open(ROOT / "data" / "annotations" / p["export"], encoding="utf-8"))
        project = api(url, token, "POST", "/api/projects", {
            "title": p["title"], "description": p["description"],
            "label_config": p["setup"].LABEL_CONFIG, "expert_instruction": p["setup"].INSTRUCTION,
            "show_instruction": True, "maximum_annotations": 2, **p["extra"]})
        pid = project["id"]
        if p["storage"]:
            api(url, token, "POST", "/api/storages/localfiles", {
                "project": pid, "title": "Разговоры", "path": str(p["storage"]), "use_blob_urls": False})
        api(url, token, "POST", f"/api/projects/{pid}/import", [to_import(t, emails) for t in tasks])
        n = sum(len(t["annotations"]) for t in tasks)
        print(f"{p['title']}: проект {pid}, задач {len(tasks)}, аннотаций {n} — {url}/projects/{pid}/data")


if __name__ == "__main__":
    main()
