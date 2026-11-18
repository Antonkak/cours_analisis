# Ручное и искусственное обогащение данных

Курсовая работа по анализу данных: сравниваем, как ручное и искусственное обогащение датасетов влияет
на качество и устойчивость обучения моделей.

## Датасеты

| Датасет | Тип | Задача | Лицензия |
|---|---|---|---|
| [SPML Chatbot Prompt Injection](https://huggingface.co/datasets/reshabhs/SPML_Chatbot_Prompt_Injection) | текст | атака на чат-бота или нет (пара «системный промпт + сообщение пользователя») | MIT |
| [TurnBench — Dev Set](https://huggingface.co/datasets/mundo-ai/turn-benchmark-dev) | аудио | поиск концов реплик во времени в разговоре двух людей (детекция событий) | Dataset Public License v1.0 (некоммерческая) |

## Структура

```
docs/
  EDA.md                план разведочного анализа обоих датасетов
  enrichment.md         ручное обогащение SPML: источники, квоты, правила отбора
  enrichment_audio.md   ручное обогащение TurnBench: постановка, выбор источника, сбор, разметка
  codebook_spml.md      правила разметки собранных промптов
  codebook_eot.md       правила разметки реплик
data/
  manual/               собранные промпты (collected.csv), боты, источники
  manual_audio/         опись собранных разговоров, источники, задачи разметки
                        (raw/ и turns_audio/ не в git, восстанавливаются по описи)
  annotations/          выгрузки проектов Label Studio со всей разметкой (*_labelstudio.json)
                        и итоговые метки после разбора расхождений (*_labels.csv)
scripts/
  download_audio.py             скачивание аудио собранных разговоров по описи
  make_turn_tasks.py            задачи-разговоры с предразметкой отрезков речи для Label Studio
  setup_labelstudio_spml.py     проект разметки промптов в Label Studio
  setup_labelstudio_turns.py    проект разметки реплик в Label Studio
  import_labelstudio.py         оба проекта с готовой разметкой в свой Label Studio
  annotation_agreement.py       согласие аннотаторов (процент совпадений, каппа Коэна) и время разметки
```

## Библиотеки и инструменты

- Python 3.12
- numpy, scipy — чтение, нарезка и передискретизация аудио
- Label Studio 1.23 — разметка

```
pip install -r requirements.txt
```

## Как открыть и поправить разметку

Вся разметка лежит в `data/annotations/` — это выгрузки проектов Label Studio в формате JSON.
Чтобы открыть её у себя в Label Studio:

1. Установить зависимости: `pip install -r requirements.txt`.
2. Скачать аудио и подготовить дорожки разговоров (около 400 МБ, нужно только для проекта с репликами):

   ```
   python scripts/download_audio.py
   python scripts/make_turn_tasks.py
   ```

3. Запустить Label Studio с раздачей локальных файлов из `data/manual_audio`:

   ```
   set LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED=true
   set LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT=<путь к репозиторию>\data\manual_audio
   label-studio start --port 8080 --enable-legacy-api-token
   ```

4. Завести в Label Studio учётные записи обоих аннотаторов (каждый регистрируется со своей почтой).
5. Взять токен доступа (Account & Settings → Legacy Token), записать в `LS_TOKEN` и загрузить проекты:

   ```
   set LS_TOKEN=<токен>
   python scripts/import_labelstudio.py --annotator 1=<почта Егора> --annotator 4=<почта Антона>
   ```

   Номера 1 и 4 — так аннотаторы записаны в выгрузках. По почте разметка достаётся своему автору;
   если почту не указать, аннотация будет записана на того, кто запускает импорт.
6. Поправить разметку в Label Studio — каждый под своей учётной записью.
7. Выгрузить проект (Export → JSON), положить файл поверх `data/annotations/spml_labelstudio.json` или
   `data/annotations/turns_labelstudio.json` и пересчитать согласие:

   ```
   python scripts/annotation_agreement.py data/annotations/spml_labelstudio.json
   python scripts/annotation_agreement.py data/annotations/turns_labelstudio.json
   ```

   Скрипт обновит таблицу `*_labels.csv`: итоговые метки, уже проставленные после разбора расхождений,
   сохраняются, новые расхождения остаются с пустой колонкой `final_label` — их нужно разобрать по codebook.

## Как создать проекты разметки с нуля

Проекты без разметки создают `scripts/setup_labelstudio_spml.py` и `scripts/setup_labelstudio_turns.py`
(Label Studio запущен как в шаге 3, токен — в `LS_TOKEN`). После разметки — шаг 7.
