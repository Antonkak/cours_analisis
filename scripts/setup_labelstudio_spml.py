"""Создаёт в Label Studio проект разметки собранных промптов SPML и загружает задачи.

Задача — пара «системный промпт бота + пользовательский промпт», метка: безопасный (benign) или атака (attack).
Колонки intended_class и attack_type аннотаторам не показываются.

Нужно: запущенный Label Studio и токен доступа пользователя в переменной LS_TOKEN.
Запуск: python scripts/setup_labelstudio_spml.py [адрес, по умолчанию http://localhost:8080]
"""

import csv
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "data" / "manual"
URL = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080").rstrip("/")
TOKEN = os.environ["LS_TOKEN"]

LABEL_CONFIG = """
<View>
  <Header value="Системный промпт бота" size="5"/>
  <Text name="system_prompt" value="$system_prompt"/>
  <Header value="Сообщение пользователя" size="5"/>
  <Text name="user_prompt" value="$user_prompt"/>
  <Choices name="label" toName="user_prompt" choice="single-radio" showInline="true" required="true">
    <Choice value="Безопасный" alias="benign" hotkey="1"/>
    <Choice value="Атака" alias="attack" hotkey="2"/>
  </Choices>
</View>
"""

INSTRUCTION = """
<p>Каждая задача — сообщение пользователя чат-боту. Прочитайте системный промпт бота и ответьте на вопрос:
может ли бот выполнить сообщение полностью и не нарушить ни одного своего правила?</p>
<ul>
<li><b>Да — Безопасный.</b> Если бот может ответить с оговорками, это тоже безопасный.</li>
<li><b>Нет — Атака.</b> Злой умысел не обязателен: искренний вопрос, который задевает запрет бота, — тоже атака.
Просьбы забыть инструкции, показать системный промпт, стать другим ботом или заняться чем-то вне тематики бота —
всегда атака.</li>
</ul>
<p>Подробные правила по каждому боту и примеры — в codebook (docs/codebook_spml.md).
Метки напарника не смотрите. Если сомневаетесь, оставьте комментарий к задаче.</p>
<p>Клавиши: 1 — безопасный, 2 — атака.</p>
"""


def api(method, path, body=None):
    req = urllib.request.Request(
        f"{URL}{path}", method=method,
        data=json.dumps(body).encode("utf-8") if body is not None else None,
        headers={"Authorization": f"Token {TOKEN}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read() or b"{}")


def main():
    bots = {r["bot"]: r["system_prompt"]
            for r in csv.DictReader(open(ROOT / "bots.csv", encoding="utf-8", newline=""))}
    tasks = [{"data": {"id": r["id"], "bot": r["bot"], "system_prompt": bots[r["bot"]], "user_prompt": r["user_prompt"]}}
             for r in csv.DictReader(open(ROOT / "collected.csv", encoding="utf-8", newline=""))]
    project = api("POST", "/api/projects", {
        "title": "SPML: атака или нет",
        "description": "Разметка собранных пользовательских промптов: безопасный запрос или атака на бота.",
        "label_config": LABEL_CONFIG,
        "expert_instruction": INSTRUCTION,
        "show_instruction": True,
        "maximum_annotations": 2,
        # задачи в collected.csv идут по боту и классу, поэтому выдаём их в случайном порядке
        "sampling": "Uniform sampling",
    })
    pid = project["id"]
    result = api("POST", f"/api/projects/{pid}/import", tasks)
    print(f"проект {pid}: загружено задач {result.get('task_count', len(tasks))}")
    print(f"{URL}/projects/{pid}/data")


if __name__ == "__main__":
    main()
