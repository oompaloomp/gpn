"""
GPN (Газпромнефть) парсер цен на топливо.
Возвращает структурированный JSON и умеет экспортировать в файл.
Версия B: чистая сессия без хардкод-cookies + усиленный curl для GitHub Actions.
"""

import subprocess
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

from .config import TARGET_STATIONS, STATION_KEYWORDS

MSK = timezone(timedelta(hours=3))


def update_cookies(response_text: str, current_cookie_str: str) -> tuple[str, Optional[str]]:
    cookies_dict = {}
    for item in current_cookie_str.split(";"):
        if "=" in item:
            k, v = item.split("=", 1)
            cookies_dict[k.strip()] = v.strip()

    for line in response_text.replace("\r", "").split("\n"):
        if line.lower().startswith("set-cookie:"):
            cookie_part = line.split(":", 1)[1].split(";")[0].strip()
            if "=" in cookie_part:
                k, v = cookie_part.split("=", 1)
                cookies_dict[k.strip()] = v.strip()

    new_str = "; ".join(f"{k}={v}" for k, v in cookies_dict.items())
    csrf = (
        cookies_dict.get("csrf-token-value")
        or cookies_dict.get("csrftoken")
        or cookies_dict.get("XSRF-TOKEN")
        or cookies_dict.get("xsrf-token")
    )
    return new_str, csrf


def run_curl(
    url: str,
    method: str = "GET",
    headers: Dict = None,
    cookie_str: str = "",
    data: str = None,
    include_headers: bool = False,
) -> str:
    """Усиленный curl: follow redirects, compression, timeout."""
    cmd = [
        "curl", "-s", "-L",
        "-X", method,
        "--max-time", "45",
        "--connect-timeout", "15",
        "--compressed",
        "--http1.1",
    ]
    if include_headers:
        cmd.append("-i")
    if headers:
        for k, v in headers.items():
            cmd.extend(["-H", f"{k}: {v}"])
    if cookie_str:
        cmd.extend(["-b", cookie_str])
    if data is not None:
        cmd.extend(["-d", data])
    cmd.append(url)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0 and not result.stdout:
        return f"CURL_ERROR_{result.returncode}: {result.stderr[:300]}"
    return result.stdout


def parse_detail_json(json_data: dict) -> Dict[str, dict]:
    fuels = {}
    items = json_data.get("data", [])
    if not isinstance(items, list):
        return fuels

    for item in items:
        if not isinstance(item, dict):
            continue

        product = item.get("product", {})
        if isinstance(product, list) and product:
            product = product[0]
        if not isinstance(product, dict):
            product = {}

        price_obj = item.get("price", {})
        if isinstance(price_obj, list) and price_obj:
            price_obj = price_obj[0]
        if not isinstance(price_obj, dict):
            price_obj = {}

        rest_obj = item.get("rest", {})
        if isinstance(rest_obj, list) and rest_obj:
            rest_obj = rest_obj[0]
        if not isinstance(rest_obj, dict):
            rest_obj = {}

        f_name = product.get("shortTitle")
        if not f_name:
            continue

        if str(f_name).upper() in ["ДТ", "ДИЗЕЛЬ", "ДТЛ"]:
            f_name = "Дизель"

        price = price_obj.get("price")
        avail = rest_obj.get("avail", False)
        delivery = rest_obj.get("delivery", "no")
        has_truck = delivery not in ("no", False, None)

        if avail:
            status = "в наличии"
        elif has_truck:
            status = "ожидается доставка"
        else:
            status = "нет"

        fuels[f_name] = {
            "price": price,
            "status": status,
            "has_truck": has_truck,
        }
    return fuels


def fetch_all_stations() -> List[Dict[str, Any]]:
    base_headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "dnt": "1",
        "origin": "https://gpnbonus.ru",
        "referer": "https://gpnbonus.ru/fuel/refuel-map",
        "sec-ch-ua": '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/148.0.0.0 Safari/537.36"
        ),
        "x-requested-with": "XMLHttpRequest",
    }

    # Чистая сессия — без хардкод cookies
    cookie_str = ""

    print("1. Получаем главную страницу и cookies (чистая сессия)...")
    main_out = run_curl(
        "https://gpnbonus.ru/",
        headers=base_headers,
        cookie_str=cookie_str,
        include_headers=True,
    )
    print(f"   Длина ответа главной: {len(main_out)} символов")
    cookie_str, csrf = update_cookies(main_out, cookie_str)
    print(f"   Cookies после главной: {cookie_str[:80]}..." if cookie_str else "   Cookies: пусто")
    print(f"   CSRF: {csrf}")

    if not csrf and "csrf" in main_out.lower():
        import re
        m = re.search(r'csrf[_-]?token["\s:=]+["\']?([a-zA-Z0-9\-_]+)', main_out, re.I)
        if m:
            csrf = m.group(1)
            print(f"   CSRF найден в HTML: {csrf[:30]}...")

    print("2. Устанавливаем регион Пермь (ID 2612857)...")
    reg_out = run_curl(
        "https://gpnbonus.ru/region/select/2612857",
        headers=base_headers,
        cookie_str=cookie_str,
        include_headers=True,
    )
    print(f"   Длина ответа региона: {len(reg_out)} символов")
    cookie_str, csrf2 = update_cookies(reg_out, cookie_str)
    if csrf2:
        csrf = csrf2
    print(f"   CSRF после региона: {csrf}")

    print("3. Скачиваем общую базу АЗС...")
    list_headers = base_headers.copy()
    list_headers["content-type"] = "application/json"
    if csrf:
        list_headers["x-csrf-token"] = csrf
        list_headers["x-csrftoken"] = csrf

    payload = (
        '{"open": false, "wash": false, "AZSShopTypeID": false, '
        '"services": {"car": {}, "payment": {}, "person": {}, "station": {}}}'
    )
    api_out = run_curl(
        "https://gpnbonus.ru/api/stations/list",
        method="POST",
        headers=list_headers,
        cookie_str=cookie_str,
        data=payload,
    )

    print("=== RAW RESPONSE (первые 500 символов) ===")
    print(repr(api_out[:500]) if api_out else "<ПУСТО>")
    print("=== END RAW ===")
    print(f"Длина ответа API: {len(api_out) if api_out else 0}")

    if not api_out or not api_out.strip() or api_out.startswith("CURL_ERROR"):
        raise RuntimeError(
            "Пустой или ошибочный ответ от /api/stations/list.\n"
            f"Ответ: {api_out[:400] if api_out else '<пусто>'}"
        )

    try:
        json_start = api_out.find("{")
        if json_start == -1:
            raise RuntimeError(f"В ответе нет JSON. Ответ: {api_out[:400]}")
        data = json.loads(api_out[json_start:])
    except Exception as e:
        raise RuntimeError(
            f"Не удалось разобрать список станций: {e}\n"
            f"Ответ сервера: {api_out[:500]}"
        )

    all_stations = data.get("stations", [])
    print(f"✅ База загружена ({len(all_stations)} АЗС). Ищем станции Перми...")

    result = []
    now = datetime.now(MSK)

    for target_id, station_name in TARGET_STATIONS.items():
        internal_id = None
        keyword = STATION_KEYWORDS[target_id]

        for st in all_stations:
            pnpo = str(st.get("PNPONumber", ""))
            name = str(st.get("name", "")).lower()
            address = str(st.get("address", "")).lower()
            region = str(st.get("regionId", ""))

            if (
                pnpo == target_id
                or f"№{target_id}" in name
                or f"n {target_id}" in name
                or f"азс {target_id}" in name
            ):
                if keyword in address or keyword in name or region == "2612857":
                    internal_id = st.get("GPNAZSID") or st.get("id")
                    break

        station_data = {
            "id": target_id,
            "name": station_name,
            "address": "",
            "time": now.strftime("%H:%M"),
            "fuels": {},
        }

        if not internal_id:
            station_data["error"] = "АЗС не найдена в регионе"
            result.append(station_data)
            continue

        det_headers = list_headers.copy()
        det_headers["content-length"] = "0"
        det_out = run_curl(
            f"https://gpnbonus.ru/api/stations/{internal_id}",
            method="POST",
            headers=det_headers,
            cookie_str=cookie_str,
            data="",
        )

        try:
            det_json_start = det_out.find("{")
            if det_json_start == -1:
                station_data["error"] = "Пустой ответ карточки"
                result.append(station_data)
                continue

            det_data = json.loads(det_out[det_json_start:])
            fuels = parse_detail_json(det_data)

            normalized = {}
            for key in ["92", "95", "G-92", "G-95", "G-100", "Дизель"]:
                if key in fuels:
                    normalized[key] = fuels[key]
                elif key == "Дизель" and "ДТл" in fuels:
                    normalized[key] = fuels["ДТл"]
                else:
                    normalized[key] = {
                        "price": None,
                        "status": "нет",
                        "has_truck": False,
                    }
            station_data["fuels"] = normalized
        except Exception as e:
            station_data["error"] = f"Ошибка карточки: {e}"

        result.append(station_data)

    return result


def get_stations_json() -> dict:
    stations = fetch_all_stations()
    return {
        "updated_at": datetime.now(MSK).isoformat(),
        "stations": stations,
    }


def _load_previous(path: Path) -> dict:
    """Читает предыдущий stations.json для расчёта available_since."""
    if not path.exists():
        return {}
    try:
        prev = json.loads(path.read_text(encoding="utf-8"))
        by_id = {}
        for st in prev.get("stations", []):
            by_id[str(st.get("id"))] = st.get("fuels") or {}
        return by_id
    except Exception:
        return {}


def _apply_available_since(stations: list, previous: dict, now_iso: str) -> list:
    """
    Для топлива со статусом «в наличии»:
    - если раньше его не было / не было в наличии → available_since = now
    - если уже было в наличии → сохраняем старый available_since
    - если сейчас нет → поле убираем
    """
    for st in stations:
        sid = str(st.get("id"))
        prev_fuels = previous.get(sid) or {}
        fuels = st.get("fuels") or {}
        for name, f in fuels.items():
            if f.get("status") == "в наличии":
                prev_f = prev_fuels.get(name) or {}
                if prev_f.get("status") == "в наличии" and prev_f.get("available_since"):
                    f["available_since"] = prev_f["available_since"]
                else:
                    f["available_since"] = now_iso
            else:
                f.pop("available_since", None)
        st["fuels"] = fuels
    return stations


def export_to_json(path: str | Path = "data/stations.json") -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    previous = _load_previous(path)
    data = get_stations_json()
    now_iso = data["updated_at"]
    data["stations"] = _apply_available_since(data["stations"], previous, now_iso)

    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="GPN fuel price parser")
    parser.add_argument("--export", action="store_true", help="Экспорт в data/stations.json")
    parser.add_argument("--pretty", action="store_true", help="Красивый вывод JSON")
    args = parser.parse_args()

    if args.export:
        p = export_to_json()
        print(f"✅ Данные сохранены в {p}")
    else:
        data = get_stations_json()
        print(json.dumps(data, ensure_ascii=False, indent=2 if args.pretty else None))
