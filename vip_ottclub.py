import time
import re
import requests
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
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

def wait_for_otp_code(session, max_wait=300):
    """Чекає 6-значний OTP-код у листі від OTTclub."""
    print(f"[*] Очікуємо OTP-код на пошті (максимум {max_wait} секунд)...")
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
            if i % 4 == 0:
                print(f"[*] Перевірка пошти (спроба {i+1})... Коду ще немає.")
        except Exception:
            continue
    return None

def get_clean_options():
    options = uc.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1366,768")
    options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--incognito")
    return options

print("[*] Ініціалізація серверного браузера...")
driver = None
options = get_clean_options()

try:
    driver = uc.Chrome(options=options, version_main=148, use_subprocess=True)
    wait = WebDriverWait(driver, 40)
    print("[+] Серверний Chrome успішно запустився!")
except Exception:
    driver = uc.Chrome(options=options, use_subprocess=True)
    wait = WebDriverWait(driver, 40)

try:
    # ── 1. Пошта ─────────────────────────────────────────────────────────────
    email_addr, py_session = get_temp_email()
    if not email_addr:
        raise Exception("Не вдалося отримати тимчасову пошту")
    print(f"[+] Тимчасова пошта: {email_addr}")

    # ── 2. Ввід пошти ────────────────────────────────────────────────────────
    driver.get("https://ottclub.tv")
    time.sleep(5)

    email_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email'], input[name='email']")))
    
    # Заносим почту через JS инъекцию
    driver.execute_script("arguments[0].value = arguments[1];", email_input, email_addr)
    driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", email_input)
    driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", email_input)
    print("[+] Email введено в поле")
    time.sleep(2)

    # ── 3. Надсилання форми через ENTER (Надійно для Headless) ────────────────
    print("[*] Надсилаємо сигнал ENTER для редиректу сторінки...")
    email_input.send_keys(Keys.ENTER)
    
    # Чекаем, пока URL сменится на страницу ввода кода подтверждения (как на твоем скриншоте)
    page_redirected = False
    for _ in range(15):
        if "regform" in driver.current_url or "signup" in driver.current_url:
            print(f"[+] Сторінка успішно перенаправлена! Поточний URL: {driver.current_url}")
            page_redirected = True
            break
        time.sleep(1)
        
    if not page_redirected:
        print("[!] Попередження: Редирект по ENTER не зафіксовано, пробуємо клік по кнопці...")
        try:
            btn = driver.find_element(By.XPATH, "//*[contains(text(), 'Протестувати') or contains(text(), 'безплатно') or @type='submit']")
            driver.execute_script("arguments[0].click();", btn)
        except Exception:
            pass
    time.sleep(5)

    # ── 4. OTP Код ───────────────────────────────────────────────────────────
    otp_code = wait_for_otp_code(py_session, max_wait=300)
    if not otp_code:
        raise Exception("OTP-код не знайдено.")

    # ── 5. Введення OTP ──────────────────────────────────────────────────────
    otp_inputs = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "input.check-password__input")))
    for i, digit in enumerate(otp_code[:len(otp_inputs)]):
        driver.execute_script("arguments[0].value = arguments[1];", otp_inputs[i], digit)
        driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", otp_inputs[i])
    print("[+] OTP код успішно введено")
    time.sleep(1)

    # ── 6. Чекбокси ──────────────────────────────────────────────────────────
    try:
        checkboxes = driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")
        for cb in checkboxes:
            if not cb.is_selected():
                driver.execute_script("arguments[0].click();", cb)
    except Exception:
        pass

    # ── 7. Продовжити ────────────────────────────────────────────────────────
    continue_btn = wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(translate(text(), 'ПРОДВЖИТИ', 'продовжити'), 'продовж') or contains(translate(text(), 'CONTINUE', 'continue'), 'continu')]")))
    driver.execute_script("arguments[0].click();", continue_btn)
    print("[+] Кнопку 'Продовжити' натиснуто! Чекаємо переходу в кабінет...")
    time.sleep(12)

    # ── 8. Відкриваємо модалку профілю ───────────────────────────────────────
    print("[*] Ініціюємо клік по іконці користувача...")
    profile_trigger = wait.until(EC.presence_of_element_located((By.XPATH, "//a[contains(@href, 'popup-settings')] | //*[contains(@class, 'header__user')] | //a[descendant::use[contains(@href, 'userB')]]")))
    driver.execute_script("arguments[0].click();", profile_trigger)
    time.sleep(4)

    # ── 9. Забираємо ключ ────────────────────────────────────────────────────
    key_el = wait.until(EC.presence_of_element_located((By.ID, "subs_ottkey")))
    final_key = None
    for _ in range(10):
        raw_key = key_el.get_attribute("textContent") or ""
        raw_key = raw_key.strip()
        if len(raw_key) >= 8 and len(raw_key) <= 12 and raw_key != "E1KGAHB6XRA4":
            final_key = raw_key
            break
        time.sleep(1)

    if not final_key:
        final_key = driver.execute_script('return document.querySelector("#subs_ottkey") ? document.querySelector("#subs_ottkey").textContent.trim() : null;')

    # ── 10. Передаємо на сервер i-tv.top ─────────────────────────────────────
    if final_key and len(final_key) >= 8:
        print(f"\n==========================================\n[УСПІХ] ЗНАЙДЕНО КЛЮЧ: {final_key}\n==========================================\n")
        driver.get(MY_PANEL_URL)
        time.sleep(5)
        input_field = wait.until(EC.presence_of_element_located((By.NAME, "input_data")))
        driver.execute_script("arguments[0].value = arguments[1];", input_field, final_key)
        try:
            driver.execute_script("arguments[0].form.submit();", input_field)
        except Exception:
            driver.execute_script("document.querySelector('form').submit();")
        print("[+++] КЛЮЧ УСПІШНО ПЕРЕДАНО НА СЕРВЕР")
        time.sleep(5)
    else:
        raise Exception(f"Отримано некоректний ключ: {final_key}")

except Exception as e:
    print(f"[-] Помилка виконання: {e}")
    if driver:
        driver.save_screenshot("error_debug.png")
    raise e
finally:
    if driver:
        driver.quit()
