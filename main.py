# clean_test_solver_secure.py
# Требует: openai>=1.0.0, pillow, keyboard, pywin32
import time
import base64
from io import BytesIO
from pathlib import Path
from PIL import ImageGrab
from openai import OpenAI
import keyboard
import win32api
import win32con
import hashlib
import threading
import requests
import os

# ---------------- CONFIG ----------------
API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = "gpt-5"
INTERVAL = 1.0
RIGHT_SHIFT_KEY = "right shift"
ACTIVATION_KEY = "home"          # Клавиша, после нажатия которой вводится пароль

KEY_MAP = {
    "A": 0x90,  # NumLock
    "B": 0x14,  # CapsLock
    "C": 0x91,  # ScrollLock
}
# ----------------------------------------

PROMPT = """
You are TestSolver. Read the question from the provided image, use only the data shown, solve if needed, 
and return EXACTLY one option letter (A, B, C, D, ...) or "?" if unclear. Output only the single character.
"""

client = OpenAI(api_key=API_KEY)

# ---------- Индикация ----------
def get_toggle_state(vk_code: int) -> bool:
    return (win32api.GetKeyState(vk_code) & 1) != 0

def press_key(vk_code: int):
    win32api.keybd_event(vk_code, 0, 0, 0)
    time.sleep(0.03)
    win32api.keybd_event(vk_code, 0, win32con.KEYEVENTF_KEYUP, 0)

def set_indicator(target_on: dict):
    for vk, want_on in target_on.items():
        cur = get_toggle_state(vk)
        if cur != want_on:
            press_key(vk)

def light_for_letter(letter: str):
    letter = (letter or "?").upper()
    if letter == "?":
        target = {KEY_MAP["A"]: False, KEY_MAP["B"]: False, KEY_MAP["C"]: False}
    elif letter == "A":
        target = {KEY_MAP["A"]: True, KEY_MAP["B"]: False, KEY_MAP["C"]: False}
    elif letter == "B":
        target = {KEY_MAP["A"]: False, KEY_MAP["B"]: True, KEY_MAP["C"]: False}
    elif letter == "C":
        target = {KEY_MAP["A"]: False, KEY_MAP["B"]: False, KEY_MAP["C"]: True}
    elif letter == "D":
        target = {KEY_MAP["A"]: True, KEY_MAP["B"]: True, KEY_MAP["C"]: True}
    else:
        target = {KEY_MAP["A"]: True, KEY_MAP["B"]: False, KEY_MAP["C"]: False}
    set_indicator(target)

def blink_all(times=2, delay=0.3):
    for _ in range(times):
        set_indicator({KEY_MAP["A"]: True, KEY_MAP["B"]: True, KEY_MAP["C"]: True})
        time.sleep(delay)
        set_indicator({KEY_MAP["A"]: False, KEY_MAP["B"]: False, KEY_MAP["C"]: False})
        time.sleep(delay)

def blink_error(times=3, delay=0.15):
    for _ in range(times):
        set_indicator({KEY_MAP["A"]: False, KEY_MAP["B"]: True, KEY_MAP["C"]: False})
        time.sleep(delay)
        set_indicator({KEY_MAP["A"]: False, KEY_MAP["B"]: False, KEY_MAP["C"]: False})
        time.sleep(delay)

# ---------- Авторизация ----------
def wait_for_password():
    print(f"Ожидание нажатия {ACTIVATION_KEY} для ввода пароля...")

    while True:
        keyboard.wait(ACTIVATION_KEY)  # ждём нажатия клавиши Home
        print("Ввод пароля начался (вводи, не обязательно в консоли):")

        typed = ""
        while True:
            event = keyboard.read_event(suppress=False)
            if event.event_type == keyboard.KEY_DOWN:
                if event.name == "enter":
                    break
                elif event.name == "backspace":
                    typed = typed[:-1]
                elif len(event.name) == 1:
                    typed += event.name
                # выводим * в консоль для отладки
                print("*" * len(typed), end="\r", flush=True)

        if typed == PASSWORD:
            print("\nПароль верный! Активация...")
            blink_all(2, 0.2)
            return True
        else:
            print("\nНеверный пароль.")
            blink_error(3, 0.15)
            time.sleep(0.5)
            print(f"Попробуй снова, нажми {ACTIVATION_KEY} для нового ввода.")

# ---------- Модель ----------
def image_to_base64(img):
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8"), buf.getvalue()

def img_hash(png_bytes: bytes):
    return hashlib.sha256(png_bytes).hexdigest()

def send_request_get_letter(img_b64):
    messages = [
        {"role": "system", "content": PROMPT},
        {"role": "user", "content": [
            {"type": "text", "text": "Solve this test and reply with only the option letter:"},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
        ]}
    ]
    resp = client.chat.completions.create(model=MODEL, messages=messages)
    out = resp.choices[0].message.content.strip()
    for ch in out:
        if ch.upper() in ("?",) or ("A" <= ch.upper() <= "Z"):
            return ch.upper()
    return "?"

def get_clipboard_image():
    img = ImageGrab.grabclipboard()
    return img if img else None

def loading_animation(stop_event):
    blink_state = False
    vk_list = [KEY_MAP["A"], KEY_MAP["B"], KEY_MAP["C"]]
    while not stop_event.is_set():
        blink_state = not blink_state
        target = {vk: blink_state for vk in vk_list}
        set_indicator(target)
        time.sleep(1)
    set_indicator({vk: False for vk in vk_list})

# ---------- Основной цикл ----------
def main():
    print("TestSolver активирован. Копируй картинку и зажимай Right Shift.")
    last_hash = None
    while True:
        try:
            if not keyboard.is_pressed(RIGHT_SHIFT_KEY):
                time.sleep(INTERVAL)
                continue

            img = get_clipboard_image()
            if not img:
                print("В буфере нет изображения.")
                time.sleep(0.5)
                continue

            b64, png_bytes = image_to_base64(img)
            h = img_hash(png_bytes)
            if h == last_hash:
                print("Та же картинка — пропускаю.")
                time.sleep(0.5)
                continue

            print("Картинка найдена, отправка...")
            stop_event = threading.Event()
            anim_thread = threading.Thread(target=loading_animation, args=(stop_event,), daemon=True)
            anim_thread.start()

            letter = send_request_get_letter(b64)

            stop_event.set()
            anim_thread.join()
            
            print("Ответ модели:", letter)
            light_for_letter(letter)
            last_hash = h

        except KeyboardInterrupt:
            print("Выход по Ctrl+C")
            break
        except Exception as e:
            print("Ошибка:", e)
        time.sleep(0.2)

# ---------- Точка входа ----------
if __name__ == "__main__":
    main()

