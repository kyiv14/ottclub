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

def wait_for_otp_code(session, max_wait=300):
    """Чекає 6-значний OTP-код у листі від OTTclub з дебаг-логами."""
    print(f"[*] Очікуємо OTP-код на пошті (максимум {max_wait} секунд)...")
    pattern = r'\b(\d{6})\b'
    for i in range(max_wait // 5):
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
            if i % 4 == 0:
                print(f"[*] Перевірка пошти (спроба {i+1})... Коду ще немає.")
        except Exception as e:
            print(f"[!] Помилка запиту до сервера пошти: {e}")
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
    print("[*] Крок 1: Запит тимчасової пошти...")
    email_addr, py_session = get_temp_email()
    if not email_addr:
        raise Exception("Не вдалося отримати тимчасову пошту")
    print(f"[+] Використовуємо пошту: {email_addr}")

    # ── 2. Головна сторінка OTTclub ──────────────────────────────────────────
    print("[*] Крок 2: Перехід на ottclub.tv...")
    driver.get("https://ottclub.tv")
    time.sleep(5)

    try:
        accept_btn = driver.find_element(By.CSS_SELECTOR, ".cky-btn-accept")
        driver.execute_script("arguments[0].click();", accept_btn)
        print("[+] Cookie-банер закрито")
        time.sleep(1)
    except Exception:
        pass

    email_input = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email'], input[name='email']"))
    )
    email_input.clear()
    email_input.send_keys(email_addr)
    print("[+] Email успішно введено в поле")

    # ── 3. Кнопка реєстрації ─────────────────────────────────────────────────
    print("[*] Крок 3: Натискання кнопки реєстрації...")
    try:
        form = email_input.find_element(By.XPATH, "./hierarchy::form | ..//form | ancestor::form")
        driver.execute_script("arguments[0].submit();", form)
        print("[+] Форму відправлено через submit()")
    except Exception:
        hero_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit'], .hero__btn")))
        driver.execute_script("arguments[0].click();", hero_btn)
        print("[+] Кнопку реєстрації натиснуто кліком")
    
    time.sleep(5)

    # ── 4. OTP з пошти ───────────────────────────────────────────────────────
    print("[*] Крок 4: Очікування коду підтвердження (до 5 хвилин)...")
    otp_code = wait_for_otp_code(py_session, max_wait=300)
    if not otp_code:
        raise Exception("OTP-код не знайдено у листі")

    # ── 5. Вводимо OTP в поля ────────────────────────────────────────────────
    print("[*] Крок 5: Введення OTP коду в поля сайту...")
    otp_inputs = wait.until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "input.check-password__input"))
    )
    print(f"[*] Знайдено полів для вводу OTP: {len(otp_inputs)}")

    for i, digit in enumerate(otp_code[:len(otp_inputs)]):
        driver.execute_script("arguments[0].value = arguments[1];", otp_inputs[i], digit)
        driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", otp_inputs[i])
    print("[+] OTP код успішно введено")
    time.sleep(1)

    # ── 6. Checkboxes — приймаємо угоду ──────────────────────────────────────
    print("[*] Крок 6: Активація чекбоксів угоди...")
    try:
        agreement_link = driver.find_element(By.XPATH, "//a[contains(text(), 'Угоду') or contains(text(), 'Terms')]")
        parent_element = agreement_link.find_element(By.XPATH, "..")
        driver.execute_script("arguments[0].click();", parent_element)
        print("[+] Чекбокс угоди активовано через батьківський елемент")
    except Exception:
        checkboxes = driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")
        if checkboxes:
            driver.execute_script("arguments[0].click();", checkboxes[0])
            print("[+] Чекбокс активовано напряму через перший input")

    time.sleep(0.5)
    checkboxes = driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")
    for idx, cb in enumerate(checkboxes):
        if not cb.is_selected():
            driver.execute_script("arguments[0].click();", cb)
            print(f"[+] Додатково активовано обов'язковий чекбокс №{idx+1}")

    # ── 7. Кнопка "Продовжити" ────────────────────────────────────────────────
    print("[*] Крок 7: Натискання кнопки 'Продовжити'...")
    continue_btn = wait.until(
        EC.presence_of_element_located((
            By.XPATH,
            "//*[contains(translate(text(), 'ПРОДВЖИТИ', 'продовжити'), 'продовж') or contains(translate(text(), 'CONTINUE', 'continue'), 'continu')]"
        ))
    )
    driver.execute_script("arguments[0].click();", continue_btn)
    print("[+] Кнопку 'Продовжити' натиснуто! Очікуємо переходу в кабінет білінгу...")
    time.sleep(12)

    print(f"[*] Поточний URL кабінету: {driver.current_url}")

    # ── 8. ПРИМУСОВИЙ КЛІК НА ПРОФІЛЬ ЧЕРЕЗ JS ДЛЯ HEADLESS РЕЖИМУ ───────────
    print("[*] Крок 8: Емуляція відкриття модалки профілю через JS тригер...")
    try:
        # Находим кнопку-ссылку профиля в DOM-дереве
        profile_trigger = wait.until(
            EC.presence_of_element_located((By.XPATH, "//a[contains(@href, 'popup-settings') or contains(@href, 'profile')] | //*[contains(@class, 'header__user')] | //a[descendant::use[contains(@href, 'userB')]]"))
        )
        # Кликаем жестко через JS, чтобы пробить отсутствие визуального фокуса в Headless
        driver.execute_script("arguments[0].click();", profile_trigger)
        print("[+] Клікнули по профілю! Очікуємо 4 секунди на генерацію модальних даних...")
        time.sleep(4)
    except Exception as ue:
        print(f"[-] Основний тригер не зпрацював ({ue}), б'ємо по резервному SVG...")
        try:
            svg_fallback = driver.find_element(By.XPATH, "//*[local-name()='use' and contains(@href, 'userB')]/..")
            driver.execute_script("arguments[0].click();", svg_fallback)
            time.sleep(4)
        except Exception:
            pass

    # ── 9. ЗАБИРАЄМО КЛЮЧ З ID #subs_ottkey (КОНТРОЛЬ НАПОВНЕННЯ СЕРВЕРОМ) ──
    print("[*] Крок 9: Збір та перевірка контенту елемента #subs_ottkey...")
    final_key = None
    try:
        # Ждем, пока элемент встроится в структуру страницы
        key_el = wait.until(EC.presence_of_element_located((By.ID, "subs_ottkey")))
        
        # Запускаем цикл проверки контента (до 15 секунд), чтобы дождаться ответа сервера OTTclub
        for _ in range(15):
            raw_key = key_el.get_attribute("textContent") or ""
            raw_key = raw_key.strip()
            # Проверяем, что внутри лежит именно токен (8-12 символов), а не пустота
            if len(raw_key) >= 8 and len(raw_key) <= 12 and raw_key != "E1KGAHB6XRA4":
                final_key = raw_key
                break
            time.sleep(1)
            
    except Exception as ke:
        print(f"[-] Не вдалося зчитати textContent з елемента: {ke}")

    # Финальный фалбек через выполнение скрипта в контексте страницы
    if not final_key:
        final_key = driver.execute_script('return document.querySelector("#subs_ottkey") ? document.querySelector("#subs_ottkey").textContent.trim() : null;')

    if final_key and final_key != "E1KGAHB6XRA4" and len(final_key) >= 8:
        print(f"\n==========================================")
        print(f"[УСПІХ] ЗНАЙДЕНО НОВИЙ КЛЮЧ: {final_key}")
        print(f"==========================================\n")

        # ── 10. Відправляємо на i-tv.top ─────────────────────────────────────
        print("[*] Крок 10: Відправка отриманого ключа на i-tv.top...")
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

        print("[+++] КЛЮЧ УСПІШНО ПЕРЕДАНО НА СЕРВЕР!")
        time.sleep(5)
    else:
        print(f"[-] Скрипт повернув некоректний або порожній ключ: {final_key}")
        driver.save_screenshot("key_missing.png")
        raise Exception("Ключ не знайдено, завершення з помилкою")

except Exception as e:
    print(f"[-] Критична помилка під час виконання: {e}")
    if driver:
        driver.save_screenshot("error_debug.png")
    raise e

finally:
    if driver:
        driver.quit()
