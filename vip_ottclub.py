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
    """Чекає 6-значний OTP-код у листі від OTTclub."""
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
    options.add_argument("--disable-blink-features=AutomationControlled")
    return options

print("[*] Ініціалізація браузера...")
driver = None
try:
    driver = uc.Chrome(options=get_clean_options(), version_main=148, use_subprocess=True)
    wait = WebDriverWait(driver, 40)
except Exception as e:
    print(f"[*] v148 не вдалося: {e}")
    driver = uc.Chrome(options=get_clean_options(), use_subprocess=True)
    wait = WebDriverWait(driver, 40)

try:
    # ── 1. Тимчасова пошта ───────────────────────────────────────────────────
    email_addr, py_session = get_temp_email()
    if not email_addr:
        raise Exception("Не вдалося отримати тимчасову пошту")
    print(f"[+] Використовуємо пошту: {email_addr}")

    # ── 2. Головна сторінка OTTclub ──────────────────────────────────────────
    driver.get("https://ottclub.tv")
    time.sleep(5)

    # Закрити cookie-банер якщо є (клас cky-btn-accept)
    try:
        accept_btn = driver.find_element(By.CSS_SELECTOR, ".cky-btn-accept")
        driver.execute_script("arguments[0].click();", accept_btn)
        time.sleep(1)
    except Exception:
        pass

    # Email input — перший input[type=email] або input без type на головній
    email_input = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email'], input[name='email']"))
    )
    email_input.clear()
    email_input.send_keys(email_addr)
    print("[+] Email введено")

    # ── 3. Кнопка реєстрації — клас hero__btn ────────────────────────────────
    hero_btn = wait.until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "button.hero__btn, .hero__btn"))
    )
    driver.execute_script("arguments[0].click();", hero_btn)
    print("[*] Кнопку натиснуто, чекаємо /info/regform/...")
    time.sleep(5)

    # ── 4. OTP з пошти ───────────────────────────────────────────────────────
    otp_code = wait_for_otp_code(py_session, max_wait=120)
    if not otp_code:
        raise Exception("OTP-код не знайдено у листі")

    # ── 5. Вводимо OTP в поля check-password__input (6 полів type=number) ────
    otp_inputs = wait.until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "input.check-password__input"))
    )
    print(f"[*] Знайдено OTP-полів: {len(otp_inputs)}")

    for i, digit in enumerate(otp_code[:len(otp_inputs)]):
        otp_inputs[i].click()
        otp_inputs[i].send_keys(digit)
        time.sleep(0.2)
    print("[+] OTP введено")

    # ── 6. Checkboxes — приймаємо угоду ──────────────────────────────────────
    try:
        checkboxes = driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")
        for cb in checkboxes:
            if not cb.is_selected():
                driver.execute_script("arguments[0].click();", cb)
        print(f"[+] Відмічено {len(checkboxes)} checkbox(ів)")
    except Exception:
        pass

    # ── 7. Кнопка "Продовжити" ────────────────────────────────────────────────
    continue_btn = wait.until(
        EC.element_to_be_clickable((
            By.XPATH,
            "//button[contains(text(),'Продовж') or contains(text(),'Continue') or contains(text(),'Далі')]"
        ))
    )
    driver.execute_script("arguments[0].click();", continue_btn)
    print("[*] 'Продовжити' натиснуто, чекаємо /billing/...")
    time.sleep(8)

    print(f"[*] URL після підтвердження: {driver.current_url}")

    # ── 8. Відкриваємо профіль — клікаємо іконку юзера ───────────────────────
    try:
        user_icon = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".header__user, [class*='user-icon'], [class*='profile']"))
        )
        driver.execute_script("arguments[0].click();", user_icon)
        time.sleep(3)
    except Exception:
        pass

    # ── 9. Витягуємо ключ ─────────────────────────────────────────────────────
    page_source = driver.page_source

    # Шукаємо поруч з "Ключ" або "Key"
    key_match = re.search(
        r'(?:Ключ|Key)[^A-Z0-9]{0,50}([A-Z0-9]{8,12})',
        page_source
    )
    final_key = None
    if key_match:
        final_key = key_match.group(1)
    else:
        # Fallback: всі послідовності 8-12 великих літер+цифр
        skip = {"OTTCLUB", "ANDROIDTV", "APPLETV", "VIDAA", "SAMSUNG",
                "ENGLISH", "UKRAINIAN", "BILLING", "HTTPS"}
        candidates = re.findall(r'\b([A-Z0-9]{8,12})\b', page_source)
        for c in candidates:
            if c not in skip:
                final_key = c
                break

    if final_key:
        print(f"[УСПІХ] КЛЮЧ: {final_key}")

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
        driver.execute_script("document.querySelector('form').submit();")

        print("[+++] КЛЮЧ ВІДПРАВЛЕНО НА СЕРВЕР")
        time.sleep(5)
    else:
        print("[-] Ключ не знайдено")
        driver.save_screenshot("key_missing.png")

except Exception as e:
    print(f"[-] Помилка: {e}")
    if driver:
        driver.save_screenshot("error_debug.png")

finally:
    if driver:
        driver.quit()
