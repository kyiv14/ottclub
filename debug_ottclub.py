import time
import requests
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

TEMP_MAIL_URL = "https://i-tv.top/tempmail/index.php"

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

def get_clean_options():
    options = uc.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    return options

print("[*] Запуск браузера...")
driver = None
try:
    driver = uc.Chrome(options=get_clean_options(), version_main=148, use_subprocess=True)
    wait = WebDriverWait(driver, 30)
except Exception as e:
    print(f"[*] v148 не вдалося: {e}")
    driver = uc.Chrome(options=get_clean_options(), use_subprocess=True)
    wait = WebDriverWait(driver, 30)

try:
    email_addr, _ = get_temp_email()
    print(f"[+] Пошта: {email_addr}")

    # --- Крок 1: Головна сторінка ---
    driver.get("https://ottclub.tv")
    time.sleep(5)
    driver.save_screenshot("step1_homepage.png")
    with open("step1_homepage.html", "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    print("[+] Скріншот та HTML головної збережено")

    # Виводимо всі inputs та buttons
    inputs = driver.find_elements(By.TAG_NAME, "input")
    print(f"[DEBUG] Inputs на головній ({len(inputs)}):")
    for i, inp in enumerate(inputs):
        print(f"  [{i}] type={inp.get_attribute('type')} name={inp.get_attribute('name')} placeholder={inp.get_attribute('placeholder')} class={inp.get_attribute('class')}")

    buttons = driver.find_elements(By.TAG_NAME, "button")
    print(f"[DEBUG] Buttons на головній ({len(buttons)}):")
    for i, btn in enumerate(buttons):
        print(f"  [{i}] type={btn.get_attribute('type')} text='{btn.text[:50]}' class={btn.get_attribute('class')}")

    # --- Вводимо email ---
    email_input = None
    for inp in inputs:
        t = inp.get_attribute('type') or ''
        p = inp.get_attribute('placeholder') or ''
        if 'email' in t.lower() or 'email' in p.lower() or 'mail' in p.lower():
            email_input = inp
            break

    if email_input:
        email_input.clear()
        email_input.send_keys(email_addr)
        print("[+] Email введено")
        driver.save_screenshot("step2_email_entered.png")

        # Натискаємо кнопку
        submit = None
        for btn in buttons:
            txt = btn.text.lower()
            if any(w in txt for w in ['тест', 'безкошт', 'continue', 'register', 'start', 'пробн']):
                submit = btn
                break
        if not submit and buttons:
            submit = buttons[0]  # перша кнопка як fallback

        if submit:
            print(f"[+] Натискаємо кнопку: '{submit.text}'")
            driver.execute_script("arguments[0].click();", submit)
            time.sleep(5)
            driver.save_screenshot("step3_after_submit.png")
            with open("step3_after_submit.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            print(f"[+] URL після сабміту: {driver.current_url}")

            # Виводимо inputs на сторінці OTP
            inputs2 = driver.find_elements(By.TAG_NAME, "input")
            print(f"[DEBUG] Inputs на сторінці після сабміту ({len(inputs2)}):")
            for i, inp in enumerate(inputs2):
                print(f"  [{i}] type={inp.get_attribute('type')} maxlength={inp.get_attribute('maxlength')} class={inp.get_attribute('class')}")
        else:
            print("[-] Кнопка не знайдена")
    else:
        print("[-] Email input не знайдено")

except Exception as e:
    print(f"[-] Помилка: {e}")
    if driver:
        driver.save_screenshot("error_debug.png")
finally:
    if driver:
        driver.quit()
