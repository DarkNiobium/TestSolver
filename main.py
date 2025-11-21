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
import win32gui
import hashlib
import threading
import requests
import os
import ctypes
from ctypes import wintypes

# ---------------- CONFIG ----------------
API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = "gpt-5"
INTERVAL = 1.0
SCREENSHOT_KEY = "middle mouse"  # Средняя кнопка мыши для скриншота и запуска

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

# ---------- Курсор ----------
class CursorManager:
    def __init__(self):
        self.original_cursor = None
        self.loading_cursor = None
        self._setup_cursors()
    
    def _setup_cursors(self):
        # Сохраняем текущий курсор
        self.original_cursor = win32gui.LoadCursor(0, win32con.IDC_ARROW)
        
        # Создаем простой курсор загрузки (песочные часы)
        self.loading_cursor = win32gui.LoadCursor(0, win32con.IDC_WAIT)
    
    def set_loading_cursor(self):
        """Установить курсор загрузки"""
        if self.loading_cursor:
            win32gui.SetCursor(self.loading_cursor)
            ctypes.windll.user32.SetCursor(self.loading_cursor)
    
    def set_normal_cursor(self):
        """Восстановить нормальный курсор"""
        if self.original_cursor:
            win32gui.SetCursor(self.original_cursor)
            ctypes.windll.user32.SetCursor(self.original_cursor)
    
    def set_system_cursor(self, cursor_name):
        """Установить системный курсор"""
        cursor = win32gui.LoadCursor(0, cursor_name)
        win32gui.SetCursor(cursor)
        ctypes.windll.user32.SetCursor(cursor)

cursor_manager = CursorManager()

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

# ---------- Скриншот ----------
def take_screenshot():
    """Сделать скриншот всего экрана"""
    try:
        screenshot = ImageGrab.grab()
        return screenshot
    except Exception as e:
        print(f"Ошибка при создании скриншота: {e}")
        return None

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

def process_screenshot():
    """Обработать скриншот и получить ответ от модели"""
    print("Создание скриншота...")
    
    # Делаем скриншот
    img = take_screenshot()
    if not img:
        print("Не удалось создать скриншот.")
        blink_error()
        return None
    
    # Конвертируем в base64
    b64, png_bytes = image_to_base64(img)
    h = img_hash(png_bytes)
    
    print("Скриншот создан, отправка в модель...")
    
    # Устанавливаем курсор загрузки
    cursor_manager.set_loading_cursor()
    
    try:
        # Отправляем запрос к модели
        letter = send_request_get_letter(b64)
        print("Ответ модели:", letter)
        return letter
    except Exception as e:
        print("Ошибка при обращении к модели:", e)
        blink_error()
        return None
    finally:
        # Восстанавливаем нормальный курсор
        cursor_manager.set_normal_cursor()

def loading_cursor_handler(stop_event):
    """Обработчик для анимации курсора загрузки"""
    while not stop_event.is_set():
        cursor_manager.set_loading_cursor()
        time.sleep(0.1)

# ---------- Основной цикл ----------
def main():
    print(f"TestSolver активирован. Нажми '{SCREENSHOT_KEY}' для создания скриншота и обработки.")
    last_hash = None
    
    def on_middle_click(e):
        """Обработчик нажатия средней кнопки мыши"""
        if e.event_type == keyboard.KEY_DOWN and e.name == 'middle mouse':
            # Запускаем в отдельном потоке, чтобы не блокировать интерфейс
            thread = threading.Thread(target=process_and_display, daemon=True)
            thread.start()
    
    def process_and_display():
        """Обработать скриншот и отобразить результат"""
        nonlocal last_hash
        letter = process_screenshot()
        if letter:
            light_for_letter(letter)
            # Сохраняем хэш для предотвращения повторной обработки
            # В данном случае хэш не используется, так как каждый скриншот уникален
        else:
            blink_error()
    
    # Регистрируем обработчик средней кнопки мыши
    keyboard.hook(on_middle_click)
    
    print("Сервис запущен. Используйте среднюю кнопку мыши для создания скриншота.")
    print("Для выхода нажмите Ctrl+C")
    
    try:
        # Бесконечный цикл для поддержания работы программы
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Выход по Ctrl+C")
    finally:
        # Восстанавливаем курсор и отключаем обработчик
        cursor_manager.set_normal_cursor()
        keyboard.unhook_all()

# ---------- Точка входа ----------
if __name__ == "__main__":
    main()
