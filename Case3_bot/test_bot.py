# -*- coding: utf-8 -*-
"""Тестирование бота: точность распознавания и скорость ответа."""
import time
import os
import bot
import web_sources
from bot import classify, reply

# Подмена сетевого запроса сохранённым фрагментом страницы Gismeteo (тесты работают без интернета)
FIXTURE = open(os.path.join(os.path.dirname(__file__), "tests_data", "gismeteo_moscow_fragment.html"),
               encoding="utf-8").read()
CALLS = []


def fake_fetch(url, session=None):
    CALLS.append(url)
    return FIXTURE


web_sources.fetch = fake_fetch

# (фраза, ожидаемый интент). None — вопрос вне тематики (ожидается fallback).
TESTS = [
    ("Привет", "greeting"), ("Здравствуйте!", "greeting"), ("Добрый день", "greeting"),
    ("Какие документы нужны для поступления?", "documents"),
    ("Что нужно подать для поступления", "documents"),
    ("Нужен ли паспорт и аттестат?", "documents"),
    ("Есть ли заочная форма обучения?", "forms"),
    ("Можно учиться онлайн?", "forms"),
    ("Какие формы обучения есть", "forms"),
    ("Не могу войти в личный кабинет", "cabinet"),
    ("Забыл пароль от LMS", "cabinet"),
    ("Как получить доступ к платформе?", "cabinet"),
    ("Как оформить отчёт по практике?", "practice"),
    ("Где взять аттестационный лист", "practice"),
    ("Нужна справка с места практики", "practice"),
    ("Сколько стоит обучение?", "cost"),
    ("Есть ли рассрочка на оплату", "cost"),
    ("Какая цена за семестр", "cost"),
    ("Дайте номер телефона", "contacts"),
    ("Где вы находитесь? Адрес", "contacts"),
    ("Как связаться с приёмной по почте", "contacts"),
    ("Где посмотреть расписание занятий?", "schedule"),
    ("Во сколько работает университет", "schedule"),
    ("Какие есть факультеты?", "faculties"),
    ("Хочу на направление прикладная информатика", "faculties"),
    ("Спасибо!", "thanks"), ("Благодарю за помощь", "thanks"),
    ("До свидания", "bye"), ("Пока", "bye"),
    # Опечатки / нестандартные формулировки (сложные случаи)
    ("документов какие надо", "documents"),
    ("дистанционное обучение возможно?", "forms"),
    ("стоимость обучения", "cost"),
    ("когда пары", "schedule"),
    # Погода (данные с сайта)
    ("Какая сегодня погода?", "weather"),
    ("Какая погода в Казани", "weather"),
    ("Сколько градусов на улице?", "weather"),
    ("Брать ли зонт, будет дождь?", "weather"),
    ("Погода завтра в Сочи", "weather"),
    # Вне тематики
    ("Расскажи анекдот", None),
    ("Кто выиграл вчера матч?", None),
]

ok = 0
errors = []
times = []
for phrase, expected in TESTS:
    t0 = time.perf_counter()
    intent, score = classify(phrase)
    reply(phrase)
    times.append((time.perf_counter() - t0) * 1000)
    if intent == expected:
        ok += 1
    else:
        errors.append((phrase, expected, intent))

print(f"Всего тестов: {len(TESTS)}; распознано верно: {ok}; точность: {ok/len(TESTS)*100:.1f}%")
print(f"Среднее время ответа: {sum(times)/len(times):.3f} мс; максимум: {max(times):.3f} мс")
for e in errors:
    print("ОШИБКА:", e)


# ---- Проверка работы с веб-источником -------------------------------------
print("\n--- Тесты веб-источника (Gismeteo) ---")
checks = []


def check(name, cond):
    checks.append(cond)
    print(("OK   " if cond else "FAIL ") + name)


CALLS.clear()
a = reply("Какая погода?")
check("город по умолчанию — Москва, есть температура", "Москва, сейчас: +15" in a and "Gismeteo" in a)
check("запрос ушёл на страницу Москвы", CALLS[-1].endswith("/weather-moscow-4368/"))
check("в ответе есть подсказка про другой город", "другом городе" in a)

a = reply("погода в Казани")
check("город из запроса (Казань) -> нужный адрес", CALLS[-1].endswith("/weather-kazan-4364/") and "Казань" in a)

a = reply("Какая погода в Санкт-Петербурге?")
check("дефисный город (Санкт-Петербург)", CALLS[-1].endswith("/weather-sankt-peterburg-4079/"))

a = reply("погода в Нижнем Новгороде")
check("город из двух слов (Нижний Новгород)", CALLS[-1].endswith("/weather-nizhny-novgorod-4355/"))

a = reply("Какая погода завтра в Сочи")
check("прогноз на завтра", "завтра" in a and "от +8 до +16" in a and CALLS[-1].endswith("/weather-sochi-5233/"))

check("формат отрицательной температуры", web_sources.fmt_t(-2) == "−2" and web_sources.fmt_t(0) == "0"
      and web_sources.fmt_t(5) == "+5")


def broken_fetch(url, session=None):
    raise web_sources.WebSourceError("нет соединения с сайтом (ConnectionError)")


web_sources.fetch = broken_fetch
a = reply("какая погода")
check("сбой сети -> понятное сообщение, а не ошибка", a.startswith("Не удалось получить погоду"))

web_sources.fetch = lambda url, session=None: "<html><body>пусто</body></html>"
a = reply("какая погода")
check("страница изменила структуру -> понятное сообщение", "структура страницы изменилась" in a)

failed = checks.count(False)
print(f"Веб-тесты: пройдено {checks.count(True)} из {len(checks)}")
