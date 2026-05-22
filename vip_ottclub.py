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
    # СЕРВЕРНИЙ РЕЖИМ (Headless увімкнено для GitHub Actions)
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1366,768")
    # Маскування під реальний десктопний браузер
    options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    options.add_argument("--disable-blink-features=AutomationControlled")
    return options

print("[*] Ініціалізація серверного браузера...")
driver = None
options = get_clean_options()

# Гнучка ініціалізація під версію Chrome на сервері GitHub
try:
    print("[*] Спроба запуска з version_main=148...")
    driver = uc.Chrome(options=options, version_main=148, use_subprocess=True)
    wait = WebDriverWait(driver, 40)
    print("[+] Серверний Chrome v148 успішно запущено!")
except Exception as e:
    print(f"[!] Не вдалося запустити з фіксованою v148: {e}")
    print("[*] Пробуємо автоматичне визначення версії...")
    try:
        driver = uc.Chrome(options=options, use_subprocess=True)
        wait = WebDriverWait(driver, 40)
        print("[+] Серверний Chrome успішно запущено в авто-режимі!")
    except Exception as e2:
        print(f"[-] Критична помилка ініціалізації Chrome: {e2}")
        raise e2

try:
    # ── 1. Тимчасова пошта ───────────────────────────────────────────────────
    email_addr, py_session = get_temp_email()
    if not email_addr:
        raise Exception("Не вдалося отримати тимчасову пошту")
    print(f"[+] Використовуємо пошту: {email_addr}")

    # ── 2. Головна сторінка OTTclub ──────────────────────────────────────────
    driver.get("https://ottclub.tv")
    time.sleep(5)

    # Закрити cookie-банер, якщо є
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

    # ── 3. Кнопка реєстрації (відправка форми) ────────────────────────────────
    try:
        form = email_input.find_element(By.XPATH, "./hierarchy::form | ..//form | ancestor::form")
        driver.execute_script("arguments[0].submit();", form)
        print("[+] Форму відправлено через submit()")
    except Exception:
        hero_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit'], .hero__btn")))
        driver.execute_script("arguments[0].click();", hero_btn)
        print("[*] Кнопку реєстрації натиснуто кліком")
    
    time.sleep(5)

    # ── 4. OTP з пошти ───────────────────────────────────────────────────────
    otp_code = wait_for_otp_code(py_session, max_wait=120)
    if not otp_code:
        raise Exception("OTP-код не знайдено у листі")

    # ── 5. Вводимо OTP в поля check-password__input ─────────────────────────
    otp_inputs = wait.until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "input.check-password__input"))
    )
    print(f"[*] Знайдено OTP-полів: {len(otp_inputs)}")

    for i, digit in enumerate(otp_code[:len(otp_inputs)]):
        driver.execute_script("arguments[0].value = arguments[1];", otp_inputs[i], digit)
        driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", otp_inputs[i])
    print("[+] OTP введено через JS")
    time.sleep(1)

    # ── 6. Checkboxes — приймаємо угоду (Залізобетонний клік) ────────────────
    try:
        print("[*] Намагаємось відмітити чекбокс 'Угода користувача'...")
        try:
            agreement_link = driver.find_element(By.XPATH, "//a[contains(text(), 'Угоду') or contains(text(), 'Terms')]")
            parent_element = agreement_link.find_element(By.XPATH, "..")
            driver.execute_script("arguments[0].click();", parent_element)
            print("[+] Клікнули по батьківському елементу посилання угоди")
        except Exception:
            checkboxes = driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")
            if checkboxes:
                driver.execute_script("arguments[0].click();", checkboxes[0])
                print("[+] Чекбокс відмічено напряму через інпут і JS")

        time.sleep(0.5)
        checkboxes = driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")
        for idx, cb in enumerate(checkboxes):
            if not cb.is_selected():
                driver.execute_script("arguments[0].click();", cb)
                print(f"[+] Додатково активовано чекбокс №{idx+1}")

    except Exception as ce:
        print(f"[!] Попередження при обробці чекбоксів: {ce}")

    # ── 7. Кнопка "Продовжити" (Залізобетонний пошук та клік через JS) ──────
    print("[*] Шукаємо кнопку 'Продовжити'...")
    continue_btn = wait.until(
        EC.presence_of_element_located((
            By.XPATH,
            "//*[contains(translate(text(), 'ПРОДВЖИТИ', 'продовжити'), 'продовж') or contains(translate(text(), 'CONTINUE', 'continue'), 'continu')]"
        ))
    )
    driver.execute_script("arguments[0].click();", continue_btn)
    print("[+] Кнопку 'Продовжити' успішно натиснуто! Чекаємо переходу в білінг...")
    time.sleep(12)

    print(f"[*] Поточний URL: {driver.current_url}")

    # ── 8. КЛІК ПО ВКЛАДЦІ "Інші пристрої" ──────────────────────────────────
    try:
        print("[*] Шукаємо вкладку 'Інші пристрої'...")
        other_devices_tab = wait.until(
            EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Інші пристрої') or contains(text(), 'Other devices')]"))
        )
        driver.execute_script("arguments[0].click();", other_devices_tab)
        print("[+] Успішно перемкнулися на вкладку 'Інші пристрої'. Чекаємо появи посилання...")
        time.sleep(4)
    except Exception as te:
        print(f"[-] Не вдалося клікнути по вкладці 'Інші пристрої': {te}")

    # ── 9. ПАРСИНГ КЛЮЧА З ПОСИЛАННЯ В ТЕКСТІ ІНСТРУКЦІЇ SIPTV ──────────────
    final_key = None
    try:
        print("[*] Шукаємо текст посилання з доменом myott.top...")
        target_element = wait.until(
            EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'myott.top')]"))
        )
        
        full_text = target_element.text.strip()
        print(f"[+] Текст посилання знайдено: {full_text}")
        
        match = re.search(r'playlist/([A-Z0-9]{8,12})', full_text, re.IGNORECASE)
        if match:
            final_key = match.group(1)
            
    except Exception as ke:
        print(f"[!] Прямий пошук по тексту не вдався ({ke}). Пробуємо повний скан DOM...")
        page_source = driver.page_source
        match = re.search(r'myott\.top/playlist/([A-Z0-9]{8,12})', page_source, re.IGNORECASE)
        if match:
            final_key = match.group(1)

    # Фінальний вивід без приховування
    if final_key and final_key != "E1KGAHB6XRA4":
        print(f"\n==========================================")
        print(f"[УСПІХ] НОВИЙ КЛЮЧ З SIPTV: {final_key}")
        print(f"==========================================\n")

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
        
        try:
            target_form = input_field.find_element(By.XPATH, "./ancestor::form")
            driver.execute_script("arguments[0].submit();", target_form)
        except Exception:
            driver.execute_script("document.querySelector('form').submit();")

        print("[+++] КЛЮЧ УСПІШНО ПЕРЕДАНО НА СЕРВЕР")
        time.sleep(5)
    else:
        print(f"[-] Скрипт отримав некоректний або порожній ключ: {final_key}")
        driver.save_screenshot("key_missing.png")

except Exception as e:
    print(f"[-] Виникла помилка під час виконання: {e}")
    if driver:
        driver.save_screenshot("error_debug.png")

finally:
    if driver:
        driver.quit()
