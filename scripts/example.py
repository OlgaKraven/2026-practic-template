"""Filled single-assignment example; optional guidance is a separate deliverable."""
import json
from build import ROOT, OUT, pdf, shell, page_html, ESC

def build_example(parent):
    data=json.loads((ROOT/'content/example.json').read_text(encoding='utf-8'))
    meta={**parent, **data['meta']}
    records={}
    for name,title,key in [('example-assignment','Задание студенту','assignment'),('example-guide','Пошаговая инструкция','guide')]:
        records[key]=pdf(OUT/f'downloads/{name}.pdf',meta,data[key],title)
    (OUT/'downloads/CrystalCounter.cs').write_text(data['code'],encoding='utf-8')
    (OUT/'example-manifest.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    cards='''<div class="grid example-grid">
    <section class="card"><p class="eyebrow">01 / Обязательный материал</p><h3>Задание студенту</h3><p>Что сделать, какие условия выполнить, как проверить и что сдать. Этого достаточно, чтобы понять все требования.</p><a class="button primary" href="downloads/example-assignment.pdf">Открыть задание · PDF</a></section>
    <section class="card"><p class="eyebrow">02 / По решению преподавателя</p><h3>Полная инструкция</h3><p>Короткая теория, действия в Unity, полный код и подсказки при ошибках. Можно показать на вебинаре или выдать файлом.</p><a class="button" href="example-guide.html">Смотреть инструкцию</a><a href="downloads/example-guide.pdf">Скачать инструкцию · PDF</a></section>
    <section class="card"><p class="eyebrow">03 / Для разбора</p><h3>Образец результата</h3><p>Три состояния счётчика, пояснения и файл кода. Статичные рисунки читаются без анимации.</p><a class="button" href="example-result.html">Посмотреть образец</a></section></div>'''
    body=cards+'<aside class="notice">Это заполненный демонстрационный фрагмент одной практики, а не полная программа ПМ.12. Связь с другими практиками для него не требуется. Назначение варианта и срок сдачи преподаватель сообщает в учебной системе.</aside>'
    body+=''.join(page_html(p,i) for i,p in enumerate(data['assignment'],1))
    (OUT/'example.html').write_text(shell(meta,'example.html','Счётчик собранных предметов','Одно задание в Unity: добавление предметов, ограничение количества и повторный запуск.',body),encoding='utf-8')
    for filename,key,title in [('example-guide.html','guide','Как выполнить задание'),('example-result.html','result','Как выглядит результат')]:
        tools='<div class="downloads"><a class="button" href="example.html">← К заданию</a><a class="button" href="downloads/example-guide.pdf">Инструкция · PDF</a><a class="button" href="downloads/CrystalCounter.cs">Полный код · CrystalCounter.cs</a></div>'
        toc='<nav class="toc" aria-label="Содержание">'+''.join(f'<a href="#page-{i}">{ESC(p["title"])}</a>' for i,p in enumerate(data[key],1))+'</nav>'
        body=tools+toc+''.join(page_html(p,i) for i,p in enumerate(data[key],1))
        (OUT/filename).write_text(shell(meta,'example.html',title,'Дополнительный материал. Преподаватель решает, показать его на занятии или выдать для самостоятельной работы.',body),encoding='utf-8')
