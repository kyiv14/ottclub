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
MY_PANEL_URL   = "https://i-tv.top/uspeh/?tab=ottclub"

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

def wait_for_otp_code(session, max_wait=120):
    print("[*] Очікуємо OTP-код на пошті...")
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
    options = uc.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    # Маскування під реальний браузер для GitHub Actions
    options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    options.add_argument("--disable-blink-features=AutomationControlled")
    return options

print("[*] Ініціалізація браузера...")
driver = None
try:
    # Прибираємо жорстку прив'язку до v148, дозволяємо uc автовизначення версії
    driver = uc.Chrome(options=get_clean_options(), use_subprocess=True)
    wait = WebDriverWait(driver, 40)
except Exception as e:
    print(f"[-] Помилка запуску Chrome: {e}")
    exit(1)

try:
    # ── 1. Тимчасова пошта ───────────────────────────────────────────────────
    email_addr, py_session = get_temp_email()
    if not email_addr:
        raise Exception("Не вдалося отримати тимчасову пошту")
    print(f"[+] Використовуємо пошту: {email_addr}")

    # ── 2. Головна сторінка OTTclub ──────────────────────────────────────────
    driver.get("https://ottclub.tv")
    time.sleep(5)

    try:
        accept_btn = driver.find_element(By.CSS_SELECTOR, ".cky-btn-accept")
        driver.execute_script("arguments[0].click();", accept_btn)
        time.sleep(1)
    except Exception:
        pass

    email_input = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email'], input[name='email']"))
    )
    email_input.clear()
    email_input.send_keys(email_addr)
    print("[+] Email введено")

    # ── 3. Кнопка реєстрації (надійна відправка форми через JS) ────────────────
    try:
        # Намагаємось надіслати форму безпосередньо через input parent або знайти кнопку
        form = email_input.find_element(By.XPATH, "./hierarchy::form | ..//form | ancestor::form")
        driver.execute_script("arguments[0].submit();", form)
        print("[+] Форму відправлено через submit()")
    except Exception:
        hero_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit'], .hero__btn")))
        driver.execute_script("arguments[0].click();", hero_btn)
        print("[*] Кнопку натиснуто кліком")
    
    time.sleep(5)

    # ── 4. OTP з пошти ───────────────────────────────────────────────────────
    otp_code = wait_for_otp_code(py_session, max_wait=120)
    if not otp_code:
        raise Exception("OTP-код не знайдено у листі")

    # ── 5. Вводимо OTP в поля ────────────────────────────────────────────────
    otp_inputs = wait.until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "input.check-password__input"))
    )
    print(f"[*] Знайдено OTP-полів: {len(otp_inputs)}")

    for i, digit in enumerate(otp_code[:len(otp_inputs)]):
        driver.execute_script("arguments[0].value = arguments[1];", otp_inputs[i], digit)
        # Генеруємо подію зміни, щоб скрипти сайту зчитали введення
        driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", otp_inputs[i])
    print("[+] OTP введено через JS")
    time.sleep(1)

    # ── 6. Чекбокси (Активуємо ТІЛЬКИ перший — Угоду) ────────────────────────
    try:
        # Нам потрібно приділити увагу саме першому чекбоксу (Угода користувача)
        checkboxes = driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")
        if checkboxes:
            if not checkboxes[0].is_selected():
                driver.execute_script("arguments[0].click();", checkboxes[0])
                print("[+] Чекбокс 'Угода' відмічено")
    except Exception as ce:
        print(f"[!] Попередження при роботі з чекбоксами: {ce}")

    # ── 7. Кнопка "Продовжити" ────────────────────────────────────────────────
    # Шукаємо кнопку всередині блоку реєстрації, ігноруючи регістр тексту
    continue_btn = wait.until(
        EC.element_to_be_clickable((
            By.XPATH,
            "//button[@type='submit'] | //button[contains(translate(text(), 'ПРОДВЖИТИ', 'продовжити'), 'продовж') or contains(translate(text(), 'CONTINUE', 'continue'), 'continu')]"
        ))
    )
    driver.execute_script("arguments[0].click();", continue_btn)
    print("[*] 'Продовжити' натиснуто, чекаємо /billing/...")
    time.sleep(10)

    print(f"[*] Поточний URL: {driver.current_url}")

    # ── 8. Відкриваємо профіль ───────────────────────────────────────────────
    # На десктопній версії іконка може відрізнятись, шукаємо за лінком або класом
    try:
        user_icon = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "a[href*='profile'], .header__user, [class*='user'], [class*='profile']"))
        )
        driver.execute_script("arguments[0].click();", user_icon)
        print("[+] Профіль відкрито")
        time.sleep(5)
    except Exception as ue:
        print(f"[-] Не вдалося відкрити модалку профілю: {ue}")

    # ── 9. Витягуємо ключ ─────────────────────────────────────────────────────
    page_source = driver.page_source
    
    # Покращений регулярний вираз, стійкий до переносів рядків (\s*)
    key_match = re.search(r'(?:Ключ|Key)\s*([^A-Z0-9]{0,50})\s*([A-Z0-9]{8,12})', page_source, re.IGNORECASE)
    
    final_key = None
    if key_match:
        final_key = key_match.group(2)
    else:
        # Фалбек пошук по тексту всієї сторінки
        skip = {"OTTCLUB", "ANDROIDTV", "APPLETV", "VIDAA", "SAMSUNG", "ENGLISH", "UKRAINIAN", "BILLING", "HTTPS"}
        candidates = re.findall(r'\b([A-Z0-9]{8,12})\b', page_source)
        for c in candidates:
            if c not in skip:
                final_key = c
                break

    if final_key:
        print(f"[УСПІХ] КЛЮЧ ЗНАЙДЕНО: {final_key}")

        # ── 10. Відправляємо на i-tv.top ─────────────────────────────────────
        driver.get(MY_PANEL_URL)
        time.sleep(5)

        driver.execute_script("""
            document.querySelectorAll('#reminderOverlay, .modal-backdrop, .toast-container')
                .forEach(el => el.remove());
            document.body.style.overflow = 'auto';
        """)

        input_field = wait.until(EC.presence_of_element_located((By.NAME, "input_data")))
        driver.execute_script("arguments[0].value = arguments[1];", input_field, final_key)
        
        # Відправляємо форму
        try:
            form = input_field.find_element(By.XPATH, "./ancestor::form")
            driver.execute_script("arguments[0].submit();", form)
        except Exception:
            driver.execute_script("document.querySelector('form').submit();")

        print("[+++] КЛЮЧ УСПІШНО ВІДПРАВЛЕНО НА СЕРВЕР")
        time.sleep(5)
    else:
        print("[-] Ключ не знайдено в DOM структурі сторінки")
        driver.save_screenshot("key_missing.png")

except Exception as e:
    print(f"[-] Виникла помилка: {e}")
    if driver:
        driver.save_screenshot("error_debug.png")

finally:
    if driver:
        driver.quit()
