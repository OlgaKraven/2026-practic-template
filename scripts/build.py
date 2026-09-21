"""Build an offline teacher site and two landscape student PDFs from one source."""
import argparse
import html
import json
import re
import shutil
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "site"
ESC = html.escape

def validate(data, release=False):
    required = ["title", "subtitle", "version", "status", "organization", "specialty", "group", "module", "hours", "environment", "variant_count", "practices", "pages", "variants"]
    for key in required:
        if key not in data or data[key] in ("", None, []):
            raise ValueError(f"Отсутствует обязательное поле: {key}")
    if data["status"] not in ("template", "ready"):
        raise ValueError("status должен быть template или ready")
    ids = [p["id"] for p in data["practices"]]
    if len(set(ids)) != len(ids) or not all(re.fullmatch(r"[a-z][a-z0-9-]*", p) for p in ids):
        raise ValueError("Идентификаторы практик должны быть уникальными латинскими slug")
    for practice in data["practices"]:
        for key in ("title", "dates", "type", "input", "new", "output"):
            if not practice.get(key):
                raise ValueError(f"Практика {practice['id']}: нет {key}")
    if len(data["variants"]) != data["variant_count"]:
        raise ValueError("Число карточек не совпадает с variant_count")
    if [v["number"] for v in data["variants"]] != list(range(1, data["variant_count"] + 1)):
        raise ValueError("Номера вариантов должны идти подряд от 1")
    for v in data["variants"]:
        for key in ("title", "context", "objects", "rule", "success", "checks", "progression"):
            if not v.get(key):
                raise ValueError(f"Вариант {v['number']}: нет {key}")
        if set(v["progression"]) != set(ids) or not all(v["progression"].values()):
            raise ValueError(f"Вариант {v['number']}: нарушена связь с практиками")
    for page in data["pages"]:
        if not page.get("title") or not page.get("kicker") or not page.get("blocks"):
            raise ValueError("Учебная страница должна иметь title, kicker, blocks")
        for b in page["blocks"]:
            if not b.get("title") or not b.get("text") or b.get("kind", "text") not in ("text", "code", "note"):
                raise ValueError("Блок должен иметь title, text и допустимый kind")
    if release:
        text = json.dumps(data, ensure_ascii=False)
        if data["status"] != "ready" or "ЗАПОЛНИТЬ" in text:
            raise ValueError("Выдача запрещена: заполните поля ЗАПОЛНИТЬ и установите status=ready")
        rules = [v["rule"].strip().casefold() for v in data["variants"]]
        if len(set(rules)) != len(rules):
            raise ValueError("Индивидуальные правила вариантов повторяются")

def b(title, text, kind="text"):
    return {"title": title, "text": text, "kind": kind}

def pages_for(data):
    pages = list(data["pages"])
    passport = {"title": "Реквизиты и рабочая среда", "kicker": "Паспорт / Данные комплекта", "blocks": [
        b("Организация и специальность", data["organization"] + "\n" + data["specialty"]),
        b("Группа, модуль и объём", data["group"] + "\n" + data["module"] + "\n" + data["hours"]),
        b("Рабочая среда", data["environment"]),
        b("Версия комплекта", data["version"] + ". Учебные страницы и предметные области выдаются вместе."),
    ]}
    pages.insert(2, passport)
    route = {"title": "Карта последовательных практик", "kicker": "Маршрут / Вход → новая работа → результат", "blocks": []}
    for i, p in enumerate(data["practices"], 1):
        route["blocks"].append(b(f"{i:02}. {p['title']}", f"{p['type']} · {p['dates']}\nВход: {p['input']}\nНовая работа: {p['new']}\nВыход: {p['output']}"))
    pages.insert(3, route)
    areas = [{"title": "Предметные области и варианты", "kicker": "Отдельный блок / Индивидуальные условия", "blocks": [
        b("Как использовать", "Номер варианта назначает преподаватель. Он сохраняется во всей цепочке практик. Общие требования находятся в документе «Учебные страницы»; карточка уточняет индивидуальные правила."),
        b("Что содержит карточка", "Контекст задачи, объекты и исходные данные, особое правило, условия успеха и отказа, новые результаты каждой практики, контрольные сценарии."),
        b("Статус карточек" if data['status'] == 'template' else "Индивидуальные условия", f"В этом шаблоне подготовлено {data['variant_count']} карточек для заполнения. Это места для будущих заданий, а не {data['variant_count']} готовых вариантов. Сначала задайте сопоставимую сложность, затем заполните каждую карточку." if data['status'] == 'template' else "Выполняйте условия назначенного варианта вместе с общими требованиями практики. Сохраняйте номер варианта в отчёте и в именах сдаваемых файлов.", "note"),
        b("Доступность материалов", "Все обязательные исходные данные должны находиться в комплекте учебной системы. Для выполнения задания студенту не требуется доступ к GitHub или к сайту преподавателя."),
    ]}]
    for v in data["variants"]:
        blocks = [b("Контекст и задача", v["context"]), b("Объекты и исходные данные", v["objects"]), b("Индивидуальное правило", v["rule"]), b("Успех и отказ", v["success"])]
        blocks += [b(f"Практика {i}: {p['title']}", v["progression"][p["id"]]) for i, p in enumerate(data["practices"], 1)]
        blocks += [b("Контрольные сценарии", v["checks"])]
        areas.append({"title": f"Вариант {v['number']:02}. {v['title']}", "kicker": "Предметная область / Сквозное индивидуальное задание", "blocks": blocks, "anchor": f"variant-{v['number']:02}"})
    return pages, areas

def fonts():
    candidates = [
        (Path("C:/Windows/Fonts"), "arial.ttf", "arialbd.ttf", "consola.ttf"),
        (Path("/usr/share/fonts/truetype/dejavu"), "DejaVuSans.ttf", "DejaVuSans-Bold.ttf", "DejaVuSansMono.ttf"),
    ]
    for root, regular, bold, mono in candidates:
        if all((root / x).exists() for x in (regular, bold, mono)):
            for name, file in [("Body", regular), ("Bold", bold), ("Mono", mono)]:
                pdfmetrics.registerFont(TTFont(name, str(root / file)))
            return
    raise RuntimeError("Нужны системные шрифты Arial/Consolas (Windows) или DejaVu (Linux)")

def pdf(path, data, pages, name):
    W, H = 841.89, 595.28  # A4 landscape, points
    margin, gap = 38, 28
    colw = (W - 2 * margin - gap) / 2
    c = canvas.Canvas(str(path), pagesize=(W, H))
    c.setTitle(f"{name} · {data['title']}")
    c.setAuthor(data["organization"])
    body = ParagraphStyle("body", fontName="Body", fontSize=13.5, leading=19, textColor=colors.HexColor("#30343b"), splitLongWords=True)
    head = ParagraphStyle("head", fontName="Bold", fontSize=14, leading=18, textColor=colors.HexColor("#1c1c1c"))
    code = ParagraphStyle("code", fontName="Mono", fontSize=11, leading=14.5, textColor=colors.HexColor("#22252a"))
    for spec in pages:
        for block in spec["blocks"]:
            if block.get("kind") == "code":
                for line in block["text"].splitlines():
                    if pdfmetrics.stringWidth(line, "Mono", 11) > colw:
                        raise ValueError(f"Строка кода слишком длинная; разбейте выражение вручную: {spec['title']}: {line}")
    title_style = ParagraphStyle("title", fontName="Bold", fontSize=23, leading=28)
    page_no = 0
    records = []

    def frame(title, kicker, continuation=False):
        nonlocal page_no
        page_no += 1
        c.bookmarkPage(f"page-{page_no}")
        c.addOutlineEntry(title + (" · продолжение" if continuation else ""), f"page-{page_no}", level=0)
        c.setFillColor(colors.HexColor("#ed131c")); c.rect(margin, H - 35, 28, 5, fill=1, stroke=0)
        c.setFont("Bold", 8); c.setFillColor(colors.HexColor("#626975"))
        c.drawString(margin + 39, H - 36, kicker[:77])
        if data["status"] == "template":
            c.drawRightString(W - margin, H - 36, "ШАБЛОН · ДЛЯ ЗАПОЛНЕНИЯ")
        p = Paragraph(ESC(title + (" · продолжение" if continuation else "")), title_style)
        _, height = p.wrap(W - 2 * margin, 100)
        p.drawOn(c, margin, H - 54 - height)
        c.setStrokeColor(colors.HexColor("#dfe1e5")); c.line(margin, 37, W - margin, 37)
        c.setFont("Body", 8); c.setFillColor(colors.HexColor("#626975"))
        c.drawString(margin, 22, f"{name} · версия {data['version']}")
        c.drawRightString(W - margin, 22, f"{page_no:02}")
        records.append({"number": page_no, "title": title, "continuation": continuation})
        return H - 72 - height

    # The cover is a teaching page, not a portrait title sheet.
    top = frame(data["title"], "Учебно-методический комплект")
    c.setFillColor(colors.HexColor("#1c1c1c")); c.roundRect(margin, top - 162, W - 2 * margin, 148, 12, fill=1, stroke=0)
    cover_style = ParagraphStyle("cover", fontName="Bold", fontSize=29, leading=35, textColor=colors.white)
    p = Paragraph(ESC(name), cover_style); _, ph = p.wrap(W - 2 * margin - 48, 100); p.drawOn(c, margin + 24, top - 40 - ph)
    c.setFont("Body", 12); c.setFillColor(colors.HexColor("#e6e6e9")); c.drawString(margin + 24, top - 133, "Теория → образец → адаптация → проверка → результат")
    meta = [data["subtitle"], data["organization"], data["specialty"], f"{data['group']} · {data['module']}", f"Объём: {data['hours']} · Версия {data['version']}"]
    y = top - 186
    for text in meta:
        p = Paragraph(ESC(text), body); _, ph = p.wrap(W - 2 * margin, 100); p.drawOn(c, margin, y - ph); y -= ph + 9
    c.showPage()

    for spec in pages:
        ytop = frame(spec["title"], spec["kicker"])
        y, col = ytop, 0
        # Balance complete blocks between columns when the semantic page fits.
        heights = []
        for block in spec["blocks"]:
            raw = ESC(block["text"]).replace("\n", "<br/>")
            if block.get("kind") == "code": raw = raw.replace(" ", "&#160;")
            heights.append(Paragraph(ESC(block["title"]), head).wrap(colw, 2000)[1] + 7 + Paragraph(raw, code if block.get("kind") == "code" else body).wrap(colw, 4000)[1] + 19)
        cut = min(range(1, len(heights)), key=lambda k: max(sum(heights[:k]), sum(heights[k:]))) if len(heights)>1 else -1
        balanced = cut > 0 and max(sum(heights[:cut]),sum(heights[cut:])) <= ytop - 54 + 19
        for block_index, block in enumerate(spec["blocks"]):
            if balanced and block_index == cut:
                col, y = 1, ytop
            kind = block.get("kind", "text")
            title = Paragraph(ESC(block["title"]), head)
            text = ESC(block["text"]).replace("\n", "<br/>")
            if kind == "code":
                text = text.replace(" ", "&#160;")
            para = Paragraph(text, code if kind == "code" else body)
            _, hh = title.wrap(colw, 100)
            _, bh = para.wrap(colw, 2000)
            needed = hh + bh + 7 if hh + bh + 7 <= ytop - 54 else hh + 48 + 18
            if y - needed < 54:
                if col == 0:
                    col, y = 1, ytop
                else:
                    c.showPage(); ytop = frame(spec["title"], spec["kicker"], True); col, y = 0, ytop
            x = margin + col * (colw + gap)
            title.drawOn(c, x, y - hh); y -= hh + 7
            pending = [para]
            while pending:
                item = pending.pop(0)
                _, ih = item.wrap(colw, 2000)
                avail = y - 54
                if ih <= avail:
                    item.drawOn(c, x, y - ih); y -= ih + 19
                else:
                    parts = item.split(colw, avail)
                    if parts:
                        _, fh = parts[0].wrap(colw, avail)
                        parts[0].drawOn(c, x, y - fh)
                        pending = parts[1:] + pending
                    else:
                        pending.insert(0, item)
                    if col == 0:
                        col, y = 1, ytop
                    else:
                        c.showPage(); ytop = frame(spec["title"], spec["kicker"], True); col, y = 0, ytop
                    x = margin + col * (colw + gap)
                    label = Paragraph(ESC(block["title"] + " · продолжение"), head)
                    _, lh = label.wrap(colw, 100); label.drawOn(c, x, y - lh); y -= lh + 7
        c.showPage()
    c.save()
    return records

def block_html(block):
    tag = "pre" if block.get("kind") == "code" else "p"
    content = ESC(block["text"])
    if tag != "pre": content = content.replace("\n", "<br>")
    return f'<section class="block {ESC(block.get("kind", "text"))}"><h3>{ESC(block["title"])}</h3><{tag}>{content}</{tag}></section>'

def page_html(page, i):
    anchor = page.get("anchor", f"page-{i}")
    return f'<article class="lesson" id="{anchor}"><p class="eyebrow">{ESC(page["kicker"])}</p><h2>{ESC(page["title"])}</h2><div class="blocks">' + "".join(block_html(b) for b in page["blocks"]) + '</div></article>'

def shell(data, active, title, lead, body):
    links = [("index.html", "Обзор"), ("lessons.html", "Учебные страницы"), ("areas.html", "Предметные области"), ("author.html", "Преподавателю")]
    nav = "".join(f'<a {"aria-current=page" if url == active else ""} href="{url}">{label}</a>' for url, label in links)
    mark = '<span class="badge">Шаблон для заполнения</span>' if data["status"] == "template" else '<span class="badge">Учебный комплект</span>'
    return f'''<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="Универсальный шаблон практик: страницы для вебинара и автономные учебные PDF."><title>{ESC(title)} · {ESC(data['title'])}</title><link rel="icon" href="assets/favicon.svg"><link rel="stylesheet" href="assets/style.css"></head><body><a class="skip" href="#main">Перейти к содержанию</a><header class="shell top"><a class="brand" href="index.html"><span class="emblem">ПР</span><span><strong>Практика / Методические материалы</strong><small>{ESC(data['subtitle'])}</small></span></a><span class="version">Версия {ESC(data['version'])}</span></header><div class="shell"><nav aria-label="Основная навигация">{nav}</nav><main id="main"><section class="hero"><p class="eyebrow">Учебный маршрут / 2026</p><h1>{ESC(title)}</h1><p>{ESC(lead)}</p>{mark}</section>{body}</main><footer><span>Материалы для обзора преподавателем</span><span>PDF A4 · альбомная ориентация · единый источник</span></footer></div></body></html>'''

def build(data):
    OUT.mkdir(exist_ok=True)
    (OUT / "downloads").mkdir(exist_ok=True)
    (OUT / "assets").mkdir(exist_ok=True)
    shutil.copyfile(ROOT / "assets/style.css", OUT / "assets/style.css")
    shutil.copyfile(ROOT / "assets/favicon.svg", OUT / "assets/favicon.svg")
    lessons, areas = pages_for(data)
    fonts()
    manifest = {
        "version": data["version"], "status": data["status"],
        "lessons": pdf(OUT / "downloads/learning-pages.pdf", data, lessons, "Учебные страницы"),
        "areas": pdf(OUT / "downloads/subject-areas.pdf", data, areas, "Предметные области"),
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    downloads = '<div class="downloads"><a class="button primary" href="downloads/learning-pages.pdf">Учебные страницы · PDF ↓</a><a class="button" href="downloads/subject-areas.pdf">Предметные области · PDF ↓</a></div>'
    cards = ''.join(f'<a class="card" href="lessons.html#page-4"><span class="eyebrow">Практика {i:02}</span><h3>{ESC(p["title"])}</h3><p>{ESC(p["new"])}</p><span class="result">Результат: {ESC(p["output"])}</span></a>' for i,p in enumerate(data["practices"],1))
    body = downloads + '<div class="intro"><h2>Один проект. Каждый этап добавляет новое.</h2><p>Теория объясняет действие, образец показывает способ решения, индивидуальный вариант требует адаптации. Готовый результат переходит в следующую практику.</p></div><div class="grid">' + cards + '</div>'
    body += '<section class="lesson"><p class="eyebrow">Два формата / Одна версия содержания</p><h2>Показать на вебинаре. Выдать в учебной системе.</h2><div class="blocks">' + block_html(b("Для преподавателя", "Обзор маршрута, последовательные учебные страницы и отдельная страница предметных областей. Все разделы доступны обычными ссылками; обязательного интерактива нет.")) + block_html(b("Для студента", "Два автономных PDF: общие учебные страницы и индивидуальные условия. Для решения не нужен доступ к репозиторию или сайту. Код и обязательные инструкции включаются в PDF полностью.")) + '</div></section>'
    body += '<aside class="notice">Текущая публикация — универсальный шаблон. 30 карточек и реквизиты требуют заполнения. Полные задания четырёх практик Unity будут подготовлены на его основе.</aside>' if data['status'] == 'template' else ''
    (OUT / "index.html").write_text(shell(data, "index.html", data["title"], "Последовательные практики, понятные учебные страницы и индивидуальные варианты для любой специальности.", body), encoding="utf-8")
    for file, title, lead, items in [("lessons.html", "Учебные страницы", "От постановки задачи к проверяемому результату. Полное содержание доступно также в PDF.", lessons), ("areas.html", "Предметные области", f"{data['variant_count']} индивидуальных карточек. Один номер варианта сохраняется во всей цепочке практик.", areas)]:
        toc = '<nav class="toc" aria-label="Содержание раздела">' + ''.join(f'<a href="#{p.get("anchor", f"page-{i}")}">{ESC(p["title"])}</a>' for i,p in enumerate(items,1)) + '</nav>'
        (OUT / file).write_text(shell(data, file, title, lead, downloads + toc + ''.join(page_html(p,i) for i,p in enumerate(items,1))), encoding="utf-8")
    author = [
        {"title": "Как собрать новую практику", "kicker": "Инструкция автору", "blocks": [
            b("1. Заполните паспорт", "В content/course.json укажите организацию, специальность, модуль, группу, часы, среду и версию. Неизвестные официальные требования уточните по рабочей программе."),
            b("2. Постройте цепочку", "Массив practices может содержать любое число практик. Для каждой задайте входной результат, новую работу и результат на выходе. Идентификаторы практик связывают их с вариантами."),
            b("3. Напишите учебные страницы", "В pages добавьте этапы: цель, теория, полный образец, действия, адаптация, проверка, ошибки, сдача. Короткий смысловой шаг оформляйте отдельной страницей. Длинный материал автоматически продолжается."),
            b("4. Заполните варианты", "В variants опишите все индивидуальные задачи. Число карточек задаётся variant_count. Для каждой практики заполните progression. Условия должны быть различными и сопоставимыми по сложности."),
        ]},
        {"title": "Сборка, проверка и выдача", "kicker": "Рабочий процесс", "blocks": [
            b("Команды", "python -m pip install -r requirements.txt\npython scripts/build.py\npython scripts/check.py\npython -m http.server 8000 --directory site", "code"),
            b("Перед выдачей студентам", "Замените все поля ЗАПОЛНИТЬ, установите status=ready и выполните python scripts/build.py --release. Сборка отклонит незаполненные поля и повторяющиеся индивидуальные правила. Содержательную корректность проверяет преподаватель."),
            b("Что загрузить в систему", "site/downloads/learning-pages.pdf и site/downloads/subject-areas.pdf. Проверьте совпадение версий, полноту исходных данных, читаемость всех страниц и список файлов для сдачи."),
            b("Как провести обзорный вебинар", "Покажите цель и итоговый продукт → карту практик → один полный учебный этап → карточку варианта → критерии и комплект сдачи. Для показа используйте сайт или альбомные PDF."),
        ]},
        {"title": "Адаптация под другие специальности", "kicker": "Повторное использование", "blocks": [
            b("Программирование", "Образец — полный код с инструкцией запуска. Проверки включают нормальные, граничные и ошибочные сценарии."),
            b("Документы и расчёты", "Образец — заполненный документ или пошаговый расчёт. Укажите исходные данные, единицы измерения, правила заполнения и контрольные значения."),
            b("Производственные операции", "Образец — последовательность действий и критерии качества. Укажите инструменты и проверенные требования безопасности из профильных документов."),
            b("Происхождение шаблона", "Структура переработана с учётом DKIP.PP.05-methodI. Визуальная основа — 2026-demo-template: красный акцент, тёмный баннер и светлые карточки. Экзаменационные таймеры и режимы тренажёра не используются."),
        ]},
    ]
    (OUT / "author.html").write_text(shell(data, "author.html", "Преподавателю", "Как наполнить шаблон, проверить автономность комплекта и подготовить выдачу.", ''.join(page_html(p,i) for i,p in enumerate(author,1))), encoding="utf-8")
    (OUT / ".nojekyll").touch()
    print(f"Built site: {len(manifest['lessons'])} learning pages, {len(manifest['areas'])} area pages")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", action="store_true", help="Reject unfinished student materials")
    args = parser.parse_args()
    data = json.loads((ROOT / "content/course.json").read_text(encoding="utf-8"))
    validate(data, args.release)
    build(data)
