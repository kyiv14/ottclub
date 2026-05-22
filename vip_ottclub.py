import time
import re
import requests
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

# --- КОНФІГУРАЦІЯ ---
TEMP_MAIL_URL = "https://i-tv.top/tempmail/index.php"
CHECK_MAIL_URL = "https://i-tv.top/tempmail/check.php"
MY_PANEL_URL   = "https://i-tv.top/uspeh/?tab=ottclub"   # <-- змініть tab якщо потрібно

OTTCLUB_URL    = "https://ottclub.tv"
REG_URL        = "https://ottclub.tv/info/regform"


def get_temp_email():
    """Отримує нову тимчасову адресу через ваш API."""
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


def wait_for_otp_code(session, max_wait=120):
    """
    Очікує лист від OTTclub і витягує 6-значний OTP-код.
    OTTclub надсилає цифровий код у тілі листа.
    """
    print("[*] Очікуємо OTP-код на пошті...")
    # OTTclub надсилає 6 цифр
    pattern = r'\b(\d{6})\b'
    for _ in range(max_wait // 5):
        time.sleep(5)
        try:
            response = session.get(
                f"{CHECK_MAIL_URL}?lang=ru&nocache={time.time()}",
                timeout=10
            )
            match = re.search(pattern, response.text)
            if match:
                code = match.group(1)
                print(f"[+] OTP-код знайдено: {code}")
                return code
        except Exception:
            continue
    return None


def get_clean_options():
    """Повертає опції для undetected-chromedriver."""
    options = uc.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    return options


# --- ЗАПУСК БРАУЗЕРА ---
print("[*] Ініціалізація браузера...")
CURRENT_CHROME_VERSION = 147
driver = None

try:
    driver = uc.Chrome(
        options=get_clean_options(),
        version_main=CURRENT_CHROME_VERSION,
        use_subprocess=True
    )
    wait = WebDriverWait(driver, 40)
except Exception as e:
    print(f"[*] Спроба №1 не вдалася: {e}")
    try:
        driver = uc.Chrome(options=get_clean_options(), use_subprocess=True)
        wait = WebDriverWait(driver, 40)
    except Exception as e2:
        print(f"[-] Критична помилка запуску: {e2}")
        exit(1)

try:
    # ── 1. Отримати тимчасову пошту ──────────────────────────────────────────
    email_addr, py_session = get_temp_email()
    if not email_addr:
        raise Exception("Не вдалося отримати тимчасову пошту")
    print(f"[+] Використовуємо пошту: {email_addr}")

    # ── 2. Відкрити головну сторінку OTTclub і ввести email ──────────────────
    driver.get(OTTCLUB_URL)
    time.sleep(4)

    # Поле email на головній сторінці (форма "Протестувати 3 дні безкоштовно")
    email_input = wait.until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='email'], input[placeholder*='email'], input[placeholder*='Email']"))
    )
    email_input.clear()
    email_input.send_keys(email_addr)

    # Натиснути кнопку реєстрації
    submit_btn = driver.find_element(
        By.CSS_SELECTOR, "button[type='submit'], input[type='submit'], button.btn-primary, button.btn-danger, button.register-btn"
    )
    submit_btn.click()
    print("[*] Email відправлено, переходимо до сторінки підтвердження...")
    time.sleep(4)

    # ── 3. Чекаємо перехід на /info/regform (сторінка введення OTP) ──────────
    # Якщо браузер ще не перейшов — підождемо
    for _ in range(10):
        if "regform" in driver.current_url or "confirm" in driver.current_url:
            break
        time.sleep(2)

    print(f"[*] Поточна URL: {driver.current_url}")

    # ── 4. Отримуємо OTP із пошти ────────────────────────────────────────────
    otp_code = wait_for_otp_code(py_session, max_wait=120)
    if not otp_code:
        raise Exception("OTP-код не знайдено у листі")

    # ── 5. Вводимо OTP по одній цифрі в 6 окремих полів ─────────────────────
    # OTTclub використовує 6 окремих <input> для коду
    otp_inputs = wait.until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "input[maxlength='1'], .otp-input, .code-input input"))
    )

    if len(otp_inputs) >= 6:
        for i, digit in enumerate(otp_code):
            otp_inputs[i].click()
            otp_inputs[i].send_keys(digit)
            time.sleep(0.2)
        print("[+] OTP введено по цифрах")
    else:
        # Якщо одне поле — вводимо весь код
        otp_inputs[0].clear()
        otp_inputs[0].send_keys(otp_code)
        print("[+] OTP введено в одне поле")

    # ── 6. Прийняти угоду користувача (checkbox) ─────────────────────────────
    try:
        checkboxes = driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")
        for cb in checkboxes:
            if not cb.is_selected():
                driver.execute_script("arguments[0].click();", cb)
        print("[+] Checkbox(и) відмічено")
    except Exception:
        pass

    # ── 7. Натиснути "Продовжити" ─────────────────────────────────────────────
    continue_btn = wait.until(
        EC.element_to_be_clickable((
            By.XPATH,
            "//button[contains(text(),'Продовжити') or contains(text(),'Continue') or contains(text(),'Submit')]"
        ))
    )
    continue_btn.click()
    print("[*] Натиснуто 'Продовжити', чекаємо переходу в білінг...")
    time.sleep(6)

    # ── 8. Відкриваємо профіль для отримання ключа ───────────────────────────
    # Після підтвердження OTTclub веде на /billing/?mes=...
    # Ключ знаходиться в профілі: кнопка-іконка юзера або /billing/profile
    print(f"[*] URL після підтвердження: {driver.current_url}")

    # Відкриваємо іконку профілю (user icon у правому верхньому куті)
    try:
        profile_icon = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "a[href*='profile'], .user-icon, svg.user, [data-target*='profile']"))
        )
        profile_icon.click()
        time.sleep(3)
    except Exception:
        # Якщо іконка не знайдена, спробуємо прямо перейти на профіль
        driver.get("https://ottclub.tv/billing/")
        time.sleep(4)

    # ── 9. Витягуємо ключ зі сторінки ────────────────────────────────────────
    page_source = driver.page_source

    # Ключ OTTclub — 9 символів, великі літери + цифри (приклад: 9JN9EZ5ZTB — 10 символів)
    # Шукаємо паттерн: 8-12 символів з великих літер і цифр, не є звичайним словом
    key_match = re.search(r'\b([A-Z0-9]{8,12})\b', page_source)

    # Уточнений пошук — шукаємо поруч з "Ключ" або "Key"
    key_context = re.search(
        r'(?:Ключ|Key|key|token)[^A-Z0-9]{0,30}([A-Z0-9]{8,12})',
        page_source
    )

    final_key = None
    if key_context:
        final_key = key_context.group(1)
    elif key_match:
        # Фільтруємо явно не ті значення
        candidates = re.findall(r'\b([A-Z0-9]{8,12})\b', page_source)
        skip = {"OTTCLUB", "ANDROIDTV", "APPLETV", "VIDAA", "SAMSUNG", "ENGLISH"}
        for c in candidates:
            if c not in skip and not c.startswith("HTTP"):
                final_key = c
                break

    if final_key:
        print(f"[УСПІХ] КЛЮЧ ЗНАЙДЕНО: {final_key}")

        # ── 10. Відправляємо ключ на i-tv.top ────────────────────────────────
        driver.get(MY_PANEL_URL)
        time.sleep(5)

        # Прибираємо можливі оверлеї
        driver.execute_script("""
            document.querySelectorAll('#reminderOverlay, .modal-backdrop, .toast-container').forEach(el => el.remove());
            document.body.style.overflow = 'auto';
        """)

        input_field = wait.until(EC.presence_of_element_located((By.NAME, "input_data")))
        driver.execute_script("arguments[0].value = arguments[1];", input_field, final_key)
        driver.execute_script("document.querySelector('form').submit();")

        print("[+++] КЛЮЧ ВІДПРАВЛЕНО НА СЕРВЕР")
        time.sleep(5)
    else:
        print("[-] Ключ не знайдено на сторінці")
        driver.save_screenshot("key_missing.png")
        print(f"[DEBUG] URL: {driver.current_url}")

except Exception as e:
    print(f"[-] Помилка: {e}")
    if driver:
        driver.save_screenshot("error_debug.png")

finally:
    if driver:
        driver.quit()
