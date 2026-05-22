import time
import re
import requests
from bs4 import BeautifulSoup

# --- КОНФІГУРАЦІЯ ---
TEMP_MAIL_URL = "https://i-tv.top/tempmail/index.php"
CHECK_MAIL_URL = "https://i-tv.top/tempmail/check.php"
MY_PANEL_URL   = "https://i-tv.top/uspeh/?tab=ottclub"

OTT_API_SEND_OTP = "https://api.ottclub.tv/api/auth/send-code"
OTT_API_VERIFY   = "https://api.ottclub.tv/api/auth/login"
OTT_API_PROFILE  = "https://api.ottclub.tv/api/user/profile"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Origin": "https://www.ottclub.tv",
    "Referer": "https://www.ottclub.tv/"
}

def get_temp_email():
    session = requests.Session()
    try:
        response = session.get(TEMP_MAIL_URL, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        email_element = soup.find(id="emailText")
        if email_element:
            return email_element.text.strip(), session
        return None, None
    except Exception as e:
        print(f"[-] Помилка отримання пошти: {e}")
        return None, None

def wait_for_otp_code(session, max_wait=180):
    """Чекає 6-значний OTP-код у листі від OTTclub."""
    print(f"[*] Очікуємо OTP-код на пошті...")
    pattern = r'\b(\d{6})\b'
    for i in range(max_wait // 5):
        time.sleep(5)
        try:
            response = session.get(f"{CHECK_MAIL_URL}?lang=ru&nocache={time.time()}", timeout=10)
            match = re.search(pattern, response.text)
            if match:
                code = match.group(1)
                print(f"[+] OTP-код знайдено: {code}")
                return code
        except Exception as e:
            continue
    return None

try:
    # ── 1. ОТРИМУЄМО ТИМЧАСОВУ ПОШТУ ─────────────────────────────────────────
    email_addr, py_session = get_temp_email()
    if not email_addr:
        raise Exception("Не вдалося отримати тимчасову пошту")
    print(f"[+] Використовуємо пошту: {email_addr}")

    # Сесія для запитів до OTTclub
    ott_session = requests.Session()
    ott_session.headers.update(HEADERS)

    # ── 2. НАДСИЛАЄМО ЗАПИТ НА ГЕНЕРАЦІЮ OTP (Імітація введення пошти) ──────
    print("[*] Надсилаємо POST-запит на генерацію OTP...")
    payload_send = {"email": email_addr, "language": "uk"}
    
    res_send = ott_session.post(OTT_API_SEND_OTP, json=payload_send, timeout=15)
    if res_send.status_code not in [200, 201]:
        raise Exception(f"API не прийняло пошту. Статус: {res_send.status_code}, Відповідь: {res_send.text}")
    print("[+] Запит на OTP успішно надіслано сервером")

    # ── 3. ОЧІКУЄМО КОД З ПОШТИ ──────────────────────────────────────────────
    otp_code = wait_for_otp_code(py_session, max_wait=180)
    if not otp_code:
        raise Exception("OTP-код не прийшов на пошту.")

    # ── 4. АВТОРІЗУЄМОСЬ ТА ОТРИМУЄМО ТОКЕН СЕСІЇ (JWT) ──────────────────────
    print("[*] Відправляємо OTP код на перевірку...")
    payload_verify = {
        "email": email_addr,
        "code": int(otp_code),
        "terms": True  # Приймаємо угоду користувача прямо в базі даних API
    }
    
    res_verify = ott_session.post(OTT_API_VERIFY, json=payload_verify, timeout=15)
    if res_verify.status_code not in [200, 201]:
        raise Exception(f"Помилка авторизації коду. Відповідь: {res_verify.text}")
    
    # Витягуємо JWT токен з відповіді сервера
    response_data = res_verify.json()
    token = response_data.get("data", {}).get("token") or response_data.get("token")
    if not token:
        raise Exception("Сервер не повернув token авторизації")
    print("[+] Авторизація успішна! Токен отримано.")

    # Оновлюємо заголовок сесії для подальших закритих запитів
    ott_session.headers.update({"Authorization": f"Bearer {token}"})

    # ── 5. ЗАБИРАЄМО ГОТОВИЙ КЛЮЧ З ПРОФІЛЮ ЧЕРЕЗ API ────────────────────────
    print("[*] Запитуємо дані профілю з бекенду...")
    res_profile = ott_session.get(OTT_API_PROFILE, timeout=15)
    if res_profile.status_code != 200:
        raise Exception(f"Не вдалося отримати профіль. Відповідь: {res_profile.text}")
    
    profile_json = res_profile.json()
    
    # Шукаємо ключ у структурі відповіді (перевіряємо можливі ключі в JSON об'єкті)
    user_data = profile_json.get("data", {})
    final_key = user_data.get("key") or user_data.get("ottkey") or user_data.get("billing_key")
    
    # Якщо сервер віддав складний JSON, підстрахуємося пошуком регуляркою по тексту відповіді
    if not final_key:
        match = re.search(r'"(?:key|ottkey|token)":"([A-Z0-9]{8,12})"', res_profile.text, re.IGNORECASE)
        if match:
            final_key = match.group(1)

    # ── 6. ВІДПРАВЛЯЄМО КЛЮЧ НА ТВІЙ СЕРВЕР I-TV.TOP ─────────────────────────
    if final_key and final_key != "E1KGAHB6XRA4":
        print(f"\n==========================================")
        print(f"[УСПІХ] ЗНАЙДЕНО НОВИЙ КЛЮЧ ЧЕРЕЗ API: {final_key}")
        print(f"==========================================\n")

        print("[*] Передаємо новий ключ на i-tv.top...")
        panel_res = requests.post(MY_PANEL_URL, data={"input_data": final_key}, timeout=15)
        print(f"[+++] КЛЮЧ УСПІШНО ПЕРЕДАНО НА СЕРВЕР! Статус відповіді: {panel_res.status_code}")
    else:
        print(f"[-] Не вдалося розпарсити ключ з JSON відповіді: {res_profile.text}")

except Exception as e:
    print(f"[-] Критична помилка виконання API-скрипта: {e}")
