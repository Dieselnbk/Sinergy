# -*- coding: utf-8 -*-
"""
Получение данных из интернета для ответов бота.

Погода запрашивается у сервиса wttr.in одним HTTP-запросом:
    https://wttr.in/<город>?format=j1&lang=ru
Ключ и регистрация не нужны. Используется только стандартная библиотека Python
(urllib + json), сторонние модули не требуются.

Особенности:
  * кэш ответов на 10 минут, чтобы не нагружать сервис;
  * таймаут и обработка ошибок — при сбое бот отвечает понятным сообщением;
  * загрузка (fetch_json) отделена от разбора (weather_answer), поэтому
    в тестах сеть подменяется сохранённым ответом.
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

WTTR = "https://wttr.in/{query}?format=j1&lang=ru"
TIMEOUT = 8          # секунд
CACHE_TTL = 600      # секунд

# Города: название в вопросе -> (как показывать в ответе, запрос к сервису).
# Показываем своё название: сервис иногда возвращает название района или пригорода,
# но координаты и температура относятся к городу.
CITIES = {
    "москва": ("Москва", "Moscow,Russia"),
    "санкт-петербург": ("Санкт-Петербург", "Saint Petersburg,Russia"),
    "питер": ("Санкт-Петербург", "Saint Petersburg,Russia"),
    "спб": ("Санкт-Петербург", "Saint Petersburg,Russia"),
    "казань": ("Казань", "Kazan,Russia"),
    "новосибирск": ("Новосибирск", "Novosibirsk,Russia"),
    "екатеринбург": ("Екатеринбург", "Yekaterinburg,Russia"),
    "сочи": ("Сочи", "Sochi,Russia"),
    "краснодар": ("Краснодар", "Krasnodar,Russia"),
    "самара": ("Самара", "Samara,Russia"),
    "уфа": ("Уфа", "Ufa,Russia"),
    "челябинск": ("Челябинск", "Chelyabinsk,Russia"),
    "воронеж": ("Воронеж", "Voronezh,Russia"),
    "владивосток": ("Владивосток", "Vladivostok,Russia"),
    "нижний новгород": ("Нижний Новгород", "Nizhny Novgorod,Russia"),
    "ростов-на-дону": ("Ростов-на-Дону", "Rostov-on-Don,Russia"),
}
DEFAULT_CITY = "москва"   # головной офис университета

_cache = {}   # url -> (время, данные)


class WebSourceError(Exception):
    """Не удалось получить или разобрать данные."""


def fetch_json(url):
    """Загрузка JSON по адресу с кэшем. Бросает WebSourceError при сбоях."""
    now = time.time()
    hit = _cache.get(url)
    if hit and now - hit[0] < CACHE_TTL:
        return hit[1]
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise WebSourceError(f"сервис вернул код {e.code}")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise WebSourceError("нет соединения с сервисом погоды")
    except ValueError:
        raise WebSourceError("сервис вернул непонятный ответ")
    _cache[url] = (now, data)
    return data


def fmt_t(v):
    """Температура как +15, −2, 0."""
    return f"{v:+d}".replace("-", "−") if v else "0"


def _ru(node, default=""):
    """Описание погоды на русском из поля lang_ru."""
    try:
        return node["lang_ru"][0]["value"].lower()
    except (KeyError, IndexError, TypeError):
        return default


def weather_answer(city_key=None, tomorrow=False):
    """Готовый текст ответа о погоде."""
    name, query = CITIES[city_key or DEFAULT_CITY]
    data = fetch_json(WTTR.format(query=urllib.parse.quote(query)))
    try:
        if tomorrow:
            day = data["weather"][1]
            desc = _ru(day["hourly"][4])          # описание на середину дня
            return (f"{name}, завтра: от {fmt_t(int(day['mintempC']))} до {fmt_t(int(day['maxtempC']))} °C"
                    + (f", {desc}" if desc else "") + ". (Источник: wttr.in)")
        cur = data["current_condition"][0]
        today = data["weather"][0]
        wind = round(int(cur["windspeedKmph"]) / 3.6)          # км/ч -> м/с
        pressure = round(int(cur["pressure"]) * 0.750062)      # гПа -> мм рт. ст.
        desc = _ru(cur)
        return (f"{name}, сейчас: {fmt_t(int(cur['temp_C']))} °C "
                f"(по ощущению {fmt_t(int(cur['FeelsLikeC']))})"
                + (f", {desc}" if desc else "")
                + f", ветер {wind} м/с, влажность {cur['humidity']} %, давление {pressure} мм рт. ст. "
                f"Сегодня от {fmt_t(int(today['mintempC']))} до {fmt_t(int(today['maxtempC']))} °C. "
                "(Источник: wttr.in)")
    except (KeyError, IndexError, ValueError, TypeError):
        raise WebSourceError("сервис вернул данные в неожиданном формате")
