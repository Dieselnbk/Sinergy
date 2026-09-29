# -*- coding: utf-8 -*-
"""
Модуль получения данных с веб-страниц для ответов бота.

Сейчас реализован один источник — погода с сайта Gismeteo (разбор HTML главной
страницы города). Архитектура позволяет добавлять другие источники: достаточно
написать функцию, которая принимает запрос пользователя и возвращает строку.

Особенности:
  * кэш ответов (по умолчанию 10 минут), чтобы не нагружать сайт;
  * таймаут и обработка ошибок сети — при сбое бот отвечает понятным сообщением;
  * разбор HTML отделён от загрузки страницы (parse_gismeteo), поэтому его можно
    тестировать без интернета.
"""
import time
import requests
from bs4 import BeautifulSoup

GISMETEO = "https://www.gismeteo.ru"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept-Language": "ru-RU,ru;q=0.9",
}
TIMEOUT = 8          # секунд
CACHE_TTL = 600      # секунд

# Города: (варианты названия в запросе) -> (название для ответа, адрес на Gismeteo).
# Адреса проверены вручную (страницы существуют).
CITIES = {
    "москва": ("Москва", "/weather-moscow-4368/"),
    "санкт-петербург": ("Санкт-Петербург", "/weather-sankt-peterburg-4079/"),
    "питер": ("Санкт-Петербург", "/weather-sankt-peterburg-4079/"),
    "спб": ("Санкт-Петербург", "/weather-sankt-peterburg-4079/"),
    "казань": ("Казань", "/weather-kazan-4364/"),
    "новосибирск": ("Новосибирск", "/weather-novosibirsk-4690/"),
    "сочи": ("Сочи", "/weather-sochi-5233/"),
    "краснодар": ("Краснодар", "/weather-krasnodar-5136/"),
    "самара": ("Самара", "/weather-samara-4618/"),
    "уфа": ("Уфа", "/weather-ufa-4588/"),
    "челябинск": ("Челябинск", "/weather-chelyabinsk-4565/"),
    "нижний новгород": ("Нижний Новгород", "/weather-nizhny-novgorod-4355/"),
    "ростов-на-дону": ("Ростов-на-Дону", "/weather-rostov-na-donu-5110/"),
}
DEFAULT_CITY = "москва"   # головной офис университета

_cache = {}   # url -> (время, html)


class WebSourceError(Exception):
    """Не удалось получить или разобрать данные с сайта."""


def fetch(url, session=None):
    """Загрузка страницы с кэшем. Бросает WebSourceError при проблемах сети."""
    now = time.time()
    hit = _cache.get(url)
    if hit and now - hit[0] < CACHE_TTL:
        return hit[1]
    try:
        r = (session or requests).get(url, headers=HEADERS, timeout=TIMEOUT)
    except requests.RequestException as e:
        raise WebSourceError(f"нет соединения с сайтом ({type(e).__name__})")
    if r.status_code != 200:
        raise WebSourceError(f"сайт вернул код {r.status_code}")
    r.encoding = "utf-8"
    _cache[url] = (now, r.text)
    return r.text


def _temp(node):
    """Значение температуры из тега <temperature-value value="15">."""
    if node is None or not node.get("value"):
        return None
    try:
        return int(float(node["value"]))
    except ValueError:
        return None


def fmt_t(v):
    """+15, −2, 0 — как на сайте."""
    return f"{v:+d}".replace("-", "−") if v else "0"


def parse_gismeteo(html):
    """
    Разбор главной страницы города на Gismeteo. Возвращает словарь:
      now, feels, now_desc, today_min, today_max, tomorrow_min, tomorrow_max, tomorrow_desc
    Строится по блоку .weathertabs: вкладки «Сейчас», «Сегодня», «Завтра».
    """
    soup = BeautifulSoup(html, "html.parser")
    tabs = soup.select(".weathertabs .weathertab")
    if len(tabs) < 3:
        raise WebSourceError("структура страницы изменилась (не найдены вкладки погоды)")
    now_tab, today_tab, tomorrow_tab = tabs[0], tabs[1], tabs[2]

    now = _temp(now_tab.select_one(".weather-value temperature-value"))
    feels = _temp(now_tab.select_one(".weather-feel temperature-value"))
    if now is None:
        raise WebSourceError("не найдена текущая температура")

    def minmax(tab):
        vals = [_temp(v) for v in tab.select(".chart .value temperature-value")]
        vals = [v for v in vals if v is not None]
        return (vals[0], vals[1]) if len(vals) >= 2 else (None, None)

    t_min, t_max = minmax(today_tab)
    tm_min, tm_max = minmax(tomorrow_tab)
    return {
        "now": now, "feels": feels,
        "now_desc": now_tab.get("data-tooltip", ""),
        "today_min": t_min, "today_max": t_max,
        "tomorrow_min": tm_min, "tomorrow_max": tm_max,
        "tomorrow_desc": tomorrow_tab.get("data-tooltip", ""),
    }


def weather_answer(city_key=None, tomorrow=False, session=None):
    """Готовый текст ответа о погоде."""
    name, path = CITIES[city_key or DEFAULT_CITY]
    data = parse_gismeteo(fetch(GISMETEO + path, session))
    if tomorrow:
        return (f"{name}, завтра: от {fmt_t(data['tomorrow_min'])} до {fmt_t(data['tomorrow_max'])} °C, "
                f"{data['tomorrow_desc']}. (Источник: Gismeteo)")
    text = f"{name}, сейчас: {fmt_t(data['now'])} °C"
    if data["feels"] is not None:
        text += f" (по ощущению {fmt_t(data['feels'])})"
    if data["now_desc"]:
        text += f", {data['now_desc']}"
    if data["today_min"] is not None:
        text += f". Сегодня от {fmt_t(data['today_min'])} до {fmt_t(data['today_max'])} °C"
    return text + ". (Источник: Gismeteo)"
