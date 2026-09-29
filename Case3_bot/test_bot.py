# -*- coding: utf-8 -*-
"""Тестирование бота: точность распознавания и скорость ответа."""
import time
import json
import os
import bot
import web_sources
from bot import classify, reply

# Подмена сетевого запроса сохранённым ответом wttr.in (тесты работают без интернета)
with open(os.path.join(os.path.dirname(__file__), "tests_data", "wttr_moscow.json"), encoding="utf-8") as f:
    FIXTURE = json.load(f)
CALLS = []


def fake_fetch(url):
    CALLS.append(url)
    return FIXTURE


web_sources.fetch_json = fake_fetch

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
print("\n--- Тесты веб-источника (wttr.in) ---")
checks = []


def check(name, cond):
    checks.append(cond)
    print(("OK   " if cond else "FAIL ") + name)


CALLS.clear()
a = reply("Какая погода?")
check("город по умолчанию — Москва, есть температура", "Москва, сейчас: +15 °C (по ощущению +11), солнечно" in a)
check("в ответе ветер, влажность, давление", "ветер 3 м/с" in a and "влажность 44 %" in a and "774 мм рт. ст." in a)
check("запрос ушёл с городом Moscow", "wttr.in/Moscow%2CRussia" in CALLS[-1])
check("в ответе есть подсказка про другой город", "другом городе" in a)

a = reply("погода в Казани")
check("город из запроса (Казань) -> нужный адрес", "Kazan" in CALLS[-1] and "Казань" in a)

a = reply("Какая погода в Санкт-Петербурге?")
check("дефисный город (Санкт-Петербург)", "Saint%20Petersburg" in CALLS[-1] and "Санкт-Петербург" in a)

a = reply("погода в Нижнем Новгороде")
check("город из двух слов (Нижний Новгород)", "Nizhny%20Novgorod" in CALLS[-1] and "Нижний Новгород" in a)

a = reply("Какая погода завтра в Сочи")
check("прогноз на завтра", "завтра" in a and "от +9 до +15" in a and "Sochi" in CALLS[-1])

check("формат отрицательной температуры", web_sources.fmt_t(-2) == "−2" and web_sources.fmt_t(0) == "0"
      and web_sources.fmt_t(5) == "+5")


def broken_fetch(url):
    raise web_sources.WebSourceError("нет соединения с сервисом погоды")


web_sources.fetch_json = broken_fetch
a = reply("какая погода")
check("сбой сети -> понятное сообщение, а не ошибка", a.startswith("Не удалось получить погоду"))

web_sources.fetch_json = lambda url: {"unexpected": True}
a = reply("какая погода")
check("неожиданный формат ответа -> понятное сообщение", "неожиданном формате" in a)

failed = checks.count(False)
print(f"Веб-тесты: пройдено {checks.count(True)} из {len(checks)}")
