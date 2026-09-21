"""One public route; author scaffolding remains in the teacher section."""
import json
from build import ROOT, OUT, pdf, shell, page_html

def build_example(parent):
    data=json.loads((ROOT/'content/example.json').read_text(encoding='utf-8'))
    meta={**parent, **data['meta']}
    records={}
    for name,title,key in [('example-assignment','Задание студенту','assignment'),('example-guide','Пошаговая инструкция','guide')]:
        records[key]=pdf(OUT/f'downloads/{name}.pdf',meta,data[key],title)
    (OUT/'downloads/CrystalCounter.cs').write_text(data['code'],encoding='utf-8')
    (OUT/'example-manifest.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    def write(file,title,lead,body):
        (OUT/file).write_text(shell(meta,file,title,lead,body),encoding='utf-8')
    def pages(items):
        return ''.join(page_html(p,i) for i,p in enumerate(items,1))
    write('index.html','Одна практика — одно задание',
          'Заполненный пример «Счётчик собранных предметов» для просмотра структуры и подачи материала.',
          '<section class="lesson"><h2>Как пользоваться материалами</h2><p>Студент получает задание в PDF. Подробную инструкцию и образец преподаватель может показать или выдать дополнительно.</p><p>Разделы в меню расположены по порядку: задание, инструкция, индивидуальные условия и образец результата. Каждый материал размещён в одном разделе.</p><p>Это демонстрационный фрагмент практики Unity. Связь с другими практиками для него не требуется.</p></section>')
    write('example.html','Счётчик собранных предметов',
          'Условия, порядок выполнения и сдача одного задания.',
          '<div class="downloads"><a class="button primary" href="downloads/example-assignment.pdf">Задание студенту · PDF</a></div>'+pages(data['assignment'][:-1]))
    write('lessons.html','Как выполнить задание',
          'Дополнительная инструкция: преподаватель решает, показать её или выдать студентам.',
          '<div class="downloads"><a class="button primary" href="downloads/example-guide.pdf">Полная инструкция · PDF</a></div>'+pages(data['guide']))
    write('areas.html','Предметные области',
          'Индивидуальные условия текущего задания. Номер варианта назначает преподаватель.',
          pages(data['assignment'][-1:]))
    write('example-result.html','Как выглядит результат',
          'Статичные схемы для разбора с преподавателем.',
          '<div class="downloads"><a class="button" href="downloads/CrystalCounter.cs">Полный код · CrystalCounter.cs</a></div>'+pages(data['result']))
    (OUT/'example-guide.html').write_text('<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=lessons.html"><title>Инструкция перенесена</title></head><body><p><a href="lessons.html">Перейти к инструкции</a></p></body></html>',encoding='utf-8')
    author=OUT/'author.html'
    block='<section class="lesson"><h2>Заготовки для нового курса</h2><p>Эти файлы предназначены автору: универсальный каркас и 30 незаполненных карточек. В учебном маршруте показан заполненный пример с двумя вариантами.</p><div class="downloads"><a class="button" href="downloads/learning-pages.pdf">Каркас учебных страниц · PDF</a><a class="button" href="downloads/subject-areas.pdf">30 карточек для заполнения · PDF</a></div></section>'
    author.write_text(author.read_text(encoding='utf-8').replace('</main>',block+'</main>'),encoding='utf-8')
