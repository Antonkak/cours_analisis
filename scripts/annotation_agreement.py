"""Согласие двух аннотаторов и время разметки по выгрузке проекта Label Studio.

Выгрузка: в проекте Export → JSON, файл положить в data/annotations/.
Подходит для обоих проектов:
  - SPML: у каждой задачи одна метка (benign / attack);
  - реплики TurnBench: у задачи-разговора отрезки «Реплика спикера N». Для каждой паузы из data.pauses
    определяем, что решил аннотатор: пауза внутри отрезка — удержание (hold), граница между отрезками —
    конец реплики (eot). Дополнительно сравниваем концы реплик аннотаторов с допуском по времени.

Считает процент согласия и каппу Коэна по объектам (промптам или паузам), размеченным обоими,
и время разметки (lead_time Label Studio) по каждому аннотатору.
Пишет таблицу «объект — метки — время» рядом с выгрузкой; итоговая метка после разбора расхождений
заполняется в колонке final_label.

Запуск: python scripts/annotation_agreement.py data/annotations/<выгрузка>.json
"""

import csv
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

TOLERANCE_S = 0.5  # допуск при сравнении концов реплик
EDGE_S = 0.05  # отрезок «перекрывает» паузу, если заходит за её края хотя бы на столько


def choice_of(annotation):
    for r in annotation["result"]:
        if r.get("type") == "choices":
            return r["value"]["choices"][0]
    return None


def regions_of(annotation):
    """Отрезки реплик: {номер спикера: [(начало, конец), ...]}."""
    out = defaultdict(list)
    for r in annotation["result"]:
        if r.get("type") == "labels":
            v = r["value"]
            speaker = v["labels"][0].split()[-1]
            out[speaker].append((v["start"], v["end"]))
    return out


def pause_labels(regions, pauses):
    labels = {}
    for p in pauses:
        inside = any(s < p["start"] + EDGE_S and e > p["end"] - EDGE_S for s, e in regions.get(p["speaker"], []))
        labels[p["pause_id"]] = "hold" if inside else "eot"
    return labels


def cohen_kappa(a, b):
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(a) | set(b)) / n ** 2
    return po, (po - pe) / (1 - pe) if pe < 1 else 1.0


def ends_f1(ends_a, ends_b):
    """F1 совпадения концов реплик двух аннотаторов (один к одному, тот же спикер, допуск TOLERANCE_S)."""
    matched = 0
    for speaker in set(ends_a) | set(ends_b):
        free = sorted(ends_b.get(speaker, []))
        for t in sorted(ends_a.get(speaker, [])):
            best = min(free, key=lambda u: abs(u - t), default=None)
            if best is not None and abs(best - t) <= TOLERANCE_S:
                matched += 1
                free.remove(best)
    na = sum(len(v) for v in ends_a.values())
    nb = sum(len(v) for v in ends_b.values())
    return 2 * matched / (na + nb) if na + nb else 1.0, matched, na, nb


def main(path):
    path = Path(path)
    tasks = json.load(open(path, encoding="utf-8"))
    rows, annotators, times, f1_parts = {}, set(), defaultdict(list), []
    for t in tasks:
        anns = [a for a in t["annotations"] if not a.get("was_cancelled")]
        pauses = t["data"].get("pauses")
        per_user_ends = {}
        for a in anns:
            user = a["completed_by"]
            annotators.add(user)
            n_obj = len(pauses) if pauses else 1
            if a.get("lead_time"):
                times[user].append(a["lead_time"] / n_obj)
            if pauses:
                regions = regions_of(a)
                labels = pause_labels(regions, pauses)
                per_user_ends[user] = {s: [e for _, e in segs] for s, segs in regions.items()}
            else:
                key = t["data"].get("id") or str(t["id"])
                labels = {key: choice_of(a)}
            for key, label in labels.items():
                row = rows.setdefault(key, {"object": key})
                row[f"label_{user}"] = label
                if a.get("lead_time") and not pauses:
                    row[f"time_{user}_s"] = round(a["lead_time"], 1)
        if len(per_user_ends) == 2:
            u, v = sorted(per_user_ends)
            f1_parts.append(ends_f1(per_user_ends[u], per_user_ends[v]))

    if len(annotators) != 2:
        sys.exit(f"ожидалось два аннотатора, в выгрузке: {sorted(annotators)}")
    u1, u2 = sorted(annotators)
    rows = sorted(rows.values(), key=lambda r: r["object"])
    both = [r for r in rows if r.get(f"label_{u1}") and r.get(f"label_{u2}")]
    a = [r[f"label_{u1}"] for r in both]
    b = [r[f"label_{u2}"] for r in both]
    po, kappa = cohen_kappa(a, b)

    print(f"объектов всего: {len(rows)}, размечено обоими: {len(both)}")
    print(f"процент согласия: {po:.1%}")
    print(f"каппа Коэна: {kappa:.3f}")
    print("метки:", {u: dict(Counter(x)) for u, x in ((u1, a), (u2, b))})
    if f1_parts:
        m = sum(p[1] for p in f1_parts)
        na, nb = sum(p[2] for p in f1_parts), sum(p[3] for p in f1_parts)
        print(f"концы реплик: у {u1} — {na}, у {u2} — {nb}, совпало с допуском {TOLERANCE_S} с — {m}, "
              f"F1 = {2 * m / (na + nb):.3f}")
    for u in (u1, u2):
        if times[u]:
            unit = "паузу" if f1_parts else "задачу"
            print(f"аннотатор {u}: время на {unit} медиана {statistics.median(times[u]):.1f} с, "
                  f"среднее {statistics.mean(times[u]):.1f} с")
    diff = [r["object"] for r in both if r[f"label_{u1}"] != r[f"label_{u2}"]]
    print(f"расхождения ({len(diff)}):", ", ".join(diff))

    out = path.with_name(path.stem + "_labels.csv")
    # итоговые метки, проставленные после разбора расхождений, не теряем при пересчёте
    decided = {}
    if out.exists():
        decided = {r["object"]: r["final_label"] for r in csv.DictReader(open(out, encoding="utf-8"))
                   if r.get("final_label")}
    fields = ["object", f"label_{u1}", f"label_{u2}"]
    if not f1_parts:
        fields += [f"time_{u1}_s", f"time_{u2}_s"]
    fields.append("final_label")
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            same = r.get(f"label_{u1}") and r.get(f"label_{u1}") == r.get(f"label_{u2}")
            w.writerow({**r, "final_label": r[f"label_{u1}"] if same else decided.get(r["object"], "")})
    print(f"таблица: {out}")


if __name__ == "__main__":
    main(sys.argv[1])
