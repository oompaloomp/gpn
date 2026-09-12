import subprocess
import json
from datetime import datetime

TARGET_STATIONS = {
    "501": "Пермь Газпромнефть (Космонавтов, 59/2) АЗС N 501",
    "502": "Пермь Газпромнефть (Цимлянская, 40) АЗС N 502",
    "503": "Пермь Газпромнефть (Коммунистическая, 27а) АЗС N 503",
    "504": "Пермь Газпромнефть (Новогайвинская, 108) АЗС N 504",
    "506": "Пермь Газпромнефть (Пермь-Екатеринбург, 13 км) АЗС N 506",
    "508": "Пермь Газпромнефть (Берег Камы) АЗС N 508",
    "509": "Пермь Газпромнефть (40-летия Победы, 22) АЗС N 509",
    "510": "Пермь Газпромнефть (Ижевская, 3) АЗС N 510",
    "511": "Пермь Газпромнефть (Калинина, 75) АЗС N 511",
    "512": "Пермь Газпромнефть (Космонавта Леонова, 80) АЗС N 512",
    "513": "Пермь Газпромнефть (Усть-Сыны) АЗС N 513",
    "514": "Пермь Газпромнефть (Сибирская, 72) АЗС N 514",
    "539": "Пермь Газпромнефть (Космонавтов, 325) АЗС N 539",
    "550": "Пермь Газпромнефть (Космонавтов, 310/11) АЗС N 550",
    "551": "Пермь Газпромнефть (Куйбышева, 113б) АЗС N 551"
}

# Жесткие ключи для отсечения станций-двойников из других городов России
STATION_KEYWORDS = {
    "501": "космонавт",
    "502": "цимлянск",
    "503": "коммунист",
    "504": "новогайвинск",
    "506": "екатеринбург",
    "508": "берег",
    "509": "побед",
    "510": "ижевск",
    "511": "калинин",
    "512": "леонов",
    "513": "сын",
    "514": "сибирск",
    "539": "космонавт",
    "550": "космонавт",
    "551": "куйбышев"
}

def update_cookies(response_text, current_cookie_str):
    cookies_dict = {}
    for item in current_cookie_str.split(';'):
        if '=' in item:
            k, v = item.split('=', 1)
            cookies_dict[k.strip()] = v.strip()

    for line in response_text.replace('\r', '').split('\n'):
        if line.lower().startswith("set-cookie:"):
            cookie_part = line.split(":", 1)[1].split(";")[0].strip()
            if "=" in cookie_part:
                k, v = cookie_part.split("=", 1)
                cookies_dict[k.strip()] = v.strip()

    new_str = "; ".join([f"{k}={v}" for k, v in cookies_dict.items()])
    return new_str, cookies_dict.get("csrf-token-value") or cookies_dict.get("csrftoken")

def run_curl(url, method="GET", headers_dict={}, cookie_str="", data=None, include_headers=False):
    cmd = ["curl", "-s", "-X", method]
    if include_headers:
        cmd.append("-i")
    for k, v in headers_dict.items():
        cmd.extend(["-H", f"{k}: {v}"])
    if cookie_str:
        cmd.extend(["-b", cookie_str])
    if data is not None:
        cmd.extend(["-d", data])
    cmd.append(url)
    
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
    return result.stdout

def parse_detail_json(json_data):
    fuels = {}
    if not isinstance(json_data, dict): return fuels
    items = json_data.get("data", [])
    if not isinstance(items, list): return fuels
        
    for item in items:
        if not isinstance(item, dict): continue
            
        product = item.get("product", {})
        if isinstance(product, list) and len(product) > 0: product = product[0]
        if not isinstance(product, dict): product = {}

        price_obj = item.get("price", {})
        if isinstance(price_obj, list) and len(price_obj) > 0: price_obj = price_obj[0]
        if not isinstance(price_obj, dict): price_obj = {}

        rest_obj = item.get("rest", {})
        if isinstance(rest_obj, list) and len(rest_obj) > 0: rest_obj = rest_obj[0]
        if not isinstance(rest_obj, dict): rest_obj = {}

        f_name = product.get("shortTitle")
        if not f_name: continue
            
        if str(f_name).upper() in ["ДТ", "ДИЗЕЛЬ", "ДТЛ"]:
            f_name = "ДТл"
            
        price = price_obj.get("price")
        avail = rest_obj.get("avail", False)
        delivery = rest_obj.get("delivery", "no")
        has_truck = (delivery != "no" and delivery is not False)
        
        if avail:
            status = 'в наличии'
        elif has_truck:
            status = 'ожидается доставка'
        else:
            status = 'нет'
            
        fuels[f_name] = {
            'price': price,
            'status': status,
            'hasTruck': has_truck
        }
    return fuels

def format_station(station_name, fuels_data):
    current_time = datetime.now().strftime("%H:%M")
    lines = [f"⛽️ {station_name} ({current_time})\n"]
    
    display_fuels = ["92", "95", "G-95"]
    if "G-100" in fuels_data:
        display_fuels.append("G-100")
    display_fuels.append("Дизель")
    
    for f in display_fuels:
        site_key = "ДТл" if f == "Дизель" else f
        
        if site_key not in fuels_data:
            lines.append(f"🔴 {f} — нет")
            continue
            
        data = fuels_data[site_key]
        status = data.get('status', '')
        price = data.get('price')
        
        if status == 'в наличии' and price:
            lines.append(f"🟢 {f} — {price} ₽")
        elif status == 'ожидается доставка' or data.get('hasTruck'):
            lines.append(f"🔴 {f} — нет 🚚 ожидается доставка")
        else:
            lines.append(f"🔴 {f} — нет")
            
    return "\n".join(lines)

def get_stations_api():
    base_headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "dnt": "1",
        "origin": "https://gpnbonus.ru",
        "referer": "https://gpnbonus.ru/fuel/refuel-map",
        "sec-ch-ua": '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
        "sec-ch-ua-mobile": "?1",
        "sec-ch-ua-platform": '"Android"',
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
        "x-requested-with": "XMLHttpRequest" 
    }
    
    cookie_str = (
        "session-cookie=18d2f250614f4a8e1454922ebeb261f58744f1ed020787fc31c78435dd7e5d2109e9e8910ae3221ab22e8ae0593b4013; "
        "tmr_lvid=8f1a77329a3579090869626aaf580b3c; tmr_lvidTS=1788758458911; _ym_uid=1788758459439363059; "
        "_ym_d=1788758459; _ym_isad=2; _ym_visorc=b; mdd=1"
    )

    print("1. Получаем токен...")
    main_page_out = run_curl("https://gpnbonus.ru/", method="GET", headers_dict=base_headers, cookie_str=cookie_str, include_headers=True)
    cookie_str, csrf_token_value = update_cookies(main_page_out, cookie_str)

    print("2. Устанавливаем регион Пермь (ID 2612857)...")
    reg_out = run_curl("https://gpnbonus.ru/region/select/2612857", method="GET", headers_dict=base_headers, cookie_str=cookie_str, include_headers=True)
    cookie_str, _ = update_cookies(reg_out, cookie_str)

    print("3. Скачиваем общую базу АЗС...")
    list_headers = base_headers.copy()
    list_headers["content-type"] = "application/json"
    if csrf_token_value:
        list_headers["x-csrf-token"] = csrf_token_value
        list_headers["x-csrftoken"] = csrf_token_value

    payload_str = '{"open": false, "wash": false, "AZSShopTypeID": false, "services": {"car": {}, "payment": {}, "person": {}, "station": {}}}'
    api_out = run_curl("https://gpnbonus.ru/api/stations/list", method="POST", headers_dict=list_headers, cookie_str=cookie_str, data=payload_str, include_headers=False)
    
    try:
        json_start = api_out.find('{')
        data = json.loads(api_out[json_start:])
    except Exception as e:
        print("❌ Ошибка при разборе API:", e)
        return

    all_stations = data.get('stations', [])
    print(f"✅ База загружена ({len(all_stations)} АЗС). Ищем станции Перми...\n")
    
    result_message = ["🟦 Информация с сайта Газпромнефть\n"]
    
    for target_id, station_name in TARGET_STATIONS.items():
        internal_id = None
        expected_keyword = STATION_KEYWORDS[target_id]
        
        # УМНЫЙ ПОИСК: Защита от дубликатов АЗС в других регионах России
        for st in all_stations:
            pnpo = str(st.get('PNPONumber', ''))
            name = str(st.get('name', '')).lower()
            address = str(st.get('address', '')).lower()
            region = str(st.get('regionId', ''))
            
            # Проверяем, совпадает ли номер АЗС
            if pnpo == target_id or f"№{target_id}" in name or f"n {target_id}" in name or f"азс {target_id}" in name:
                
                # ЖЕСТКАЯ ПРОВЕРКА: Это точно наша станция, а не Московская?
                # Проверяем наличие нашей улицы в адресе, ИЛИ совпадение ID региона Перми (2612857)
                if expected_keyword in address or expected_keyword in name or region == "2612857":
                    internal_id = st.get('GPNAZSID') or st.get('id')
                    break
                
        if not internal_id:
            result_message.append(f"⛽️ {station_name}\n❌ АЗС не найдена в регионе\n")
            continue
            
        det_headers = list_headers.copy()
        det_headers["content-length"] = "0"
        
        det_out = run_curl(f"https://gpnbonus.ru/api/stations/{internal_id}", method="POST", headers_dict=det_headers, cookie_str=cookie_str, data="", include_headers=False)
        
        try:
            det_json_start = det_out.find('{')
            if det_json_start != -1:
                det_data = json.loads(det_out[det_json_start:])
                fuels_data = parse_detail_json(det_data)
                
                if fuels_data:
                    formatted = format_station(station_name, fuels_data)
                    result_message.append(formatted)
                    result_message.append("\n")
                else:
                    result_message.append(f"⛽️ {station_name}\n⚠️ Цены отсутствуют в ответе карточки\n")
            else:
                result_message.append(f"⛽️ {station_name}\n⚠️ Пустой ответ от сервера\n")
                
        except Exception:
            result_message.append(f"⛽️ {station_name}\n❌ Ошибка получения данных карточки\n")

    print("\n".join(result_message))

if __name__ == "__main__":
    get_stations_api()