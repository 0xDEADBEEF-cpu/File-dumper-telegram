import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from tkinter.font import Font
import asyncio
import threading
import json
import os
import re
from datetime import datetime
from pathlib import Path
from telethon import TelegramClient, errors
from telethon.tl.types import MessageMediaDocument, DocumentAttributeFilename
import sys
import webbrowser
from typing import List, Dict, Optional, Set
from dataclasses import dataclass
import queue
import time
import traceback

# ========== КОНСТАНТЫ ==========
ALL_EXTENSIONS = {
    'Архивы': ['.zip', '.rar', '.7z', '.bin', '.tar', '.gz', '.bz2', '.xz'],
    'Документы': ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt'],
    'Изображения': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff'],
    'Видео': ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm'],
    'Аудио': ['.mp3', '.wav', '.flac', '.ogg', '.m4a', '.aac'],
    'Исполняемые': ['.exe', '.msi', '.bat', '.sh'],
    'Другие': ['.iso', '.torrent', '.json', '.xml', '.csv']
}

EXTENSION_CATEGORIES = {
    '.zip': 'Архивы',
    '.rar': 'Архивы',
    '.7z': 'Архивы',
    '.bin': 'Архивы',
    '.tar': 'Архивы',
    '.gz': 'Архивы',
    '.bz2': 'Архивы',
    '.xz': 'Архивы',
    '.pdf': 'Документы',
    '.doc': 'Документы',
    '.docx': 'Документы',
    '.xls': 'Документы',
    '.xlsx': 'Документы',
    '.ppt': 'Документы',
    '.pptx': 'Документы',
    '.txt': 'Документы',
    '.jpg': 'Изображения',
    '.jpeg': 'Изображения',
    '.png': 'Изображения',
    '.gif': 'Изображения',
    '.bmp': 'Изображения',
    '.webp': 'Изображения',
    '.tiff': 'Изображения',
    '.mp4': 'Видео',
    '.avi': 'Видео',
    '.mkv': 'Видео',
    '.mov': 'Видео',
    '.wmv': 'Видео',
    '.flv': 'Видео',
    '.webm': 'Видео',
    '.mp3': 'Аудио',
    '.wav': 'Аудио',
    '.flac': 'Аудио',
    '.ogg': 'Аудио',
    '.m4a': 'Аудио',
    '.aac': 'Аудио',
    '.exe': 'Исполняемые',
    '.msi': 'Исполняемые',
    '.bat': 'Исполняемые',
    '.sh': 'Исполняемые',
    '.iso': 'Другие',
    '.torrent': 'Другие',
    '.json': 'Другие',
    '.xml': 'Другие',
    '.csv': 'Другие'
}

MIME_TO_EXT = {
    'application/zip': '.zip',
    'application/x-rar-compressed': '.rar',
    'application/x-7z-compressed': '.7z',
    'application/octet-stream': '.bin',
    'application/x-tar': '.tar',
    'application/gzip': '.gz',
    'application/x-bzip2': '.bz2',
    'application/x-xz': '.xz',
    'application/pdf': '.pdf',
    'application/msword': '.doc',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
    'application/vnd.ms-excel': '.xls',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
    'application/vnd.ms-powerpoint': '.ppt',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation': '.pptx',
    'text/plain': '.txt',
    'image/jpeg': '.jpg',
    'image/png': '.png',
    'image/gif': '.gif',
    'image/bmp': '.bmp',
    'image/webp': '.webp',
    'image/tiff': '.tiff',
    'video/mp4': '.mp4',
    'video/x-msvideo': '.avi',
    'video/x-matroska': '.mkv',
    'video/quicktime': '.mov',
    'video/x-ms-wmv': '.wmv',
    'video/x-flv': '.flv',
    'video/webm': '.webm',
    'audio/mpeg': '.mp3',
    'audio/wav': '.wav',
    'audio/flac': '.flac',
    'audio/ogg': '.ogg',
    'audio/mp4': '.m4a',
    'audio/aac': '.aac',
    'application/x-msdownload': '.exe',
    'application/x-msi': '.msi',
    'application/x-shellscript': '.sh',
    'application/x-iso9660-image': '.iso',
    'application/x-bittorrent': '.torrent',
    'application/json': '.json',
    'application/xml': '.xml',
    'text/csv': '.csv'
}


@dataclass
class FileInfo:
    id: int
    filename: str
    size_bytes: int
    date: datetime
    mime_type: str
    extension: str
    category: str


class AsyncTelegramClient:
    """Асинхронный клиент Telegram с правильным управлением event loop"""

    def __init__(self):
        self.client = None
        self.is_connected = False
        self.code_callback_func = None
        self.loop = None

    def create_client(self, api_id: int, api_hash: str):
        """Создание клиента Telegram"""
        self.client = TelegramClient('tg_session', api_id, api_hash)

    async def connect(self, phone: str, password: str = None, code_callback=None):
        """Подключение к Telegram"""
        try:
            self.code_callback_func = code_callback

            if code_callback:
                await self.client.start(
                    phone=phone,
                    password=password,
                    code_callback=self._code_callback_wrapper
                )
            else:
                await self.client.start(phone=phone, password=password)

            self.is_connected = True
            return True, "Успешно подключено"
        except errors.SessionPasswordNeededError:
            return False, "Требуется пароль 2FA"
        except errors.PhoneCodeInvalidError:
            return False, "Неверный код подтверждения"
        except Exception as e:
            return False, f"Ошибка подключения: {str(e)}"

    async def _code_callback_wrapper(self):
        """Обертка для callback кода"""
        if self.code_callback_func:
            return await self.code_callback_func()
        return None

    async def get_chat_info(self, chat_input: str):
        """Получение информации о чате"""
        try:
            if chat_input.startswith('https://t.me/'):
                chat_input = chat_input.replace('https://t.me/', '@')

            entity = await self.client.get_entity(chat_input)
            return True, entity
        except ValueError:
            try:
                entity = await self.client.get_entity(int(chat_input))
                return True, entity
            except:
                return False, "Не удалось найти чат. Проверьте ссылку или ID"
        except Exception as e:
            return False, f"Ошибка: {str(e)}"

    async def get_all_files(self, entity, limit: int = 25000, selected_extensions: Set[str] = None,
                            progress_callback=None):
        """Получение всех файлов из чата"""
        files = []
        total_size = 0
        processed_count = 0

        async for message in self.client.iter_messages(entity, limit=limit):
            if not self.is_connected:
                break

            processed_count += 1

            if progress_callback and processed_count % 50 == 0:
                await progress_callback(processed_count)

            try:
                if message.media and isinstance(message.media, MessageMediaDocument):
                    doc = message.media.document
                    mime_type = doc.mime_type or ''

                    # Определяем расширение
                    extension = None
                    filename = None

                    # Ищем имя файла в атрибутах
                    for attr in doc.attributes:
                        if isinstance(attr, DocumentAttributeFilename):
                            filename = attr.file_name
                            _, ext = os.path.splitext(filename.lower())
                            extension = ext
                            break

                    # Если расширение не найдено в имени файла, определяем по MIME типу
                    if not extension and mime_type:
                        extension = MIME_TO_EXT.get(mime_type, '')

                    # Если расширение найдено и оно выбрано пользователем
                    if extension and (not selected_extensions or extension in selected_extensions):
                        # Определяем категорию
                        category = EXTENSION_CATEGORIES.get(extension, 'Другие')

                        if not filename:
                            filename = f"file_{message.id}{extension}"

                        file_size = doc.size
                        total_size += file_size

                        files.append(FileInfo(
                            id=message.id,
                            filename=filename,
                            size_bytes=file_size,
                            date=message.date,
                            mime_type=mime_type,
                            extension=extension,
                            category=category
                        ))
            except Exception as e:
                print(f"Ошибка при обработке сообщения {message.id}: {str(e)}")
                continue

        return files, total_size

    async def download_file(self, chat, message_id, file_path):
        """Загрузка одного файла"""
        try:
            message = await self.client.get_messages(chat, ids=message_id)
            if message and message.media:
                await self.client.download_media(message.media, file_path)
                return True, ""
            return False, "Файл не найден"
        except Exception as e:
            return False, str(e)


class ExtensionSelector:
    """Виджет для выбора расширений файлов"""

    def __init__(self, parent):
        self.parent = parent
        self.selected_extensions = set()
        self.checkbuttons = {}
        self.category_vars = {}

    def create_widgets(self, frame):
        """Создание виджетов выбора расширений"""
        # Заголовок
        ttk.Label(frame, text="Выберите типы файлов для скачивания:",
                  font=('Arial', 11, 'bold')).pack(anchor='w', pady=(0, 10))

        # Фрейм для кнопок управления
        control_frame = ttk.Frame(frame)
        control_frame.pack(fill='x', pady=(0, 10))

        ttk.Button(control_frame, text="Выбрать все",
                   command=self.select_all).pack(side='left', padx=5)
        ttk.Button(control_frame, text="Снять все",
                   command=self.deselect_all).pack(side='left', padx=5)
        ttk.Button(control_frame, text="Только архивы",
                   command=self.select_only_archives).pack(side='left', padx=5)
        ttk.Button(control_frame, text="Только документы",
                   command=self.select_only_documents).pack(side='left', padx=5)

        # Создаем фреймы для каждой категории
        for category, extensions in ALL_EXTENSIONS.items():
            self.create_category_section(frame, category, extensions)

    def create_category_section(self, parent, category, extensions):
        """Создание секции для категории расширений"""
        # Чекбокс для всей категории
        category_frame = ttk.LabelFrame(parent, text=category, padding=5)
        category_frame.pack(fill='x', pady=5)

        # Переменная для чекбокса категории
        self.category_vars[category] = tk.BooleanVar()
        category_cb = ttk.Checkbutton(
            category_frame,
            text=f"Вся категория ({len(extensions)} расширений)",
            variable=self.category_vars[category],
            command=lambda c=category, e=extensions: self.toggle_category(c, e)
        )
        category_cb.pack(anchor='w')

        # Фрейм для расширений категории
        ext_frame = ttk.Frame(category_frame)
        ext_frame.pack(fill='x', padx=20)

        # Чекбоксы для каждого расширения
        for ext in sorted(extensions):
            var = tk.BooleanVar()
            cb = ttk.Checkbutton(
                ext_frame,
                text=ext,
                variable=var,
                command=lambda e=ext: self.update_category_checkbox(e)
            )
            cb.pack(anchor='w', padx=10)
            self.checkbuttons[ext] = var

    def select_all(self):
        """Выбрать все расширения"""
        for var in self.checkbuttons.values():
            var.set(True)
        for var in self.category_vars.values():
            var.set(True)
        self.update_selected_extensions()

    def deselect_all(self):
        """Снять выбор со всех расширений"""
        for var in self.checkbuttons.values():
            var.set(False)
        for var in self.category_vars.values():
            var.set(False)
        self.update_selected_extensions()

    def select_only_archives(self):
        """Выбрать только архивные файлы"""
        self.deselect_all()
        for ext in ALL_EXTENSIONS['Архивы']:
            if ext in self.checkbuttons:
                self.checkbuttons[ext].set(True)
        self.category_vars['Архивы'].set(True)
        self.update_selected_extensions()

    def select_only_documents(self):
        """Выбрать только документы"""
        self.deselect_all()
        for ext in ALL_EXTENSIONS['Документы']:
            if ext in self.checkbuttons:
                self.checkbuttons[ext].set(True)
        self.category_vars['Документы'].set(True)
        self.update_selected_extensions()

    def toggle_category(self, category, extensions):
        """Включить/выключить всю категорию"""
        state = self.category_vars[category].get()
        for ext in extensions:
            if ext in self.checkbuttons:
                self.checkbuttons[ext].set(state)
        self.update_selected_extensions()

    def update_category_checkbox(self, extension):
        """Обновить чекбокс категории при изменении отдельных расширений"""
        category = EXTENSION_CATEGORIES.get(extension, 'Другие')
        if category in self.category_vars:
            # Проверяем, все ли расширения категории выбраны
            category_exts = ALL_EXTENSIONS.get(category, [])
            all_selected = all(
                self.checkbuttons[ext].get()
                for ext in category_exts
                if ext in self.checkbuttons
            )
            self.category_vars[category].set(all_selected)
        self.update_selected_extensions()

    def update_selected_extensions(self):
        """Обновить выбранные расширения"""
        self.selected_extensions = {
            ext for ext, var in self.checkbuttons.items()
            if var.get()
        }

    def get_selected_extensions(self):
        """Получить выбранные расширения"""
        self.update_selected_extensions()
        return self.selected_extensions

    def load_settings(self, extensions):
        """Загрузить сохраненные настройки"""
        if extensions:
            for ext in extensions:
                if ext in self.checkbuttons:
                    self.checkbuttons[ext].set(True)
            self.update_selected_extensions()
            # Обновляем категории
            for category, exts in ALL_EXTENSIONS.items():
                if all(ext in extensions for ext in exts if ext in self.checkbuttons):
                    self.category_vars[category].set(True)


class TelegramDownloaderGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Telegram File Downloader PRO")
        self.root.geometry("1100x800")
        self.root.configure(bg='#f0f0f0')

        # Инициализация переменных
        self.client = AsyncTelegramClient()
        self.selected_files = []
        self.all_files = []
        self.total_size_mb = 0
        self.file_count = 0
        self.current_chat = None
        self.is_connected = False
        self.is_scanning = False
        self.is_downloading = False

        # Настройки
        self.settings_file = 'tg_downloader_settings.json'
        self.settings = {}

        # Инициализация селектора расширений
        self.extension_selector = ExtensionSelector(self.root)

        # Создание интерфейса
        self.setup_ui()

        # Загрузка настроек
        self.load_settings()

        # Настройка прокрутки колесиком мыши
        self.setup_mouse_wheel_scroll()

        # Для Windows настраиваем event loop policy
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        # СОЗДАЁМ LOOP ОДИН РАЗ
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        # Запускаем loop в отдельном потоке
        threading.Thread(
            target=self.loop.run_forever,
            daemon=True
        ).start()

        # Отладочные сообщения
        self.debug_queue = queue.Queue()
        self.start_debug_monitor()

    def debug_log(self, message, level="INFO"):
        """Запись отладочного сообщения"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        full_message = f"[{timestamp}] [{level}] {message}"
        self.debug_queue.put(full_message)

        # Также выводим в консоль для удобства
        print(full_message)

    def start_debug_monitor(self):
        """Запуск мониторинга отладочных сообщений"""

        def check_queue():
            try:
                while True:
                    message = self.debug_queue.get_nowait()
                    if hasattr(self, 'debug_text'):
                        self.debug_text.insert(tk.END, message + "\n")
                        self.debug_text.see(tk.END)
            except queue.Empty:
                pass
            self.root.after(100, check_queue)

        self.root.after(100, check_queue)

    def run_async_task(self, async_func, *args):
        """Запускает асинхронную функцию с правильным управлением event loop"""

        async def wrapper():
            try:
                self.debug_log(f"Запуск асинхронной задачи: {async_func.__name__}")
                result = await async_func(*args)
                self.debug_log(f"Задача {async_func.__name__} завершена успешно")
                self.root.after(0, self._on_async_complete, *result)
            except Exception as e:
                error_msg = f"Ошибка в задаче {async_func.__name__}: {str(e)}"
                self.debug_log(error_msg, "ERROR")
                self.debug_log(traceback.format_exc(), "TRACEBACK")
                self.root.after(0, self._on_async_error, str(e))

        asyncio.run_coroutine_threadsafe(wrapper(), self.loop)

    def _on_async_complete(self, *args):
        """Обработка завершения асинхронной задачи"""
        self.debug_log(f"_on_async_complete вызван с аргументами: {args}")

        if len(args) == 2:
            if args[0] == "success":
                # Это результат загрузки чата
                self._on_chat_load_success(args[1])
            elif args[0] == "error":
                # Это ошибка загрузки чата
                self._on_chat_load_error(args[1])
            elif args[0] == "estimate":
                # Это оценка размера
                self._on_estimate_complete(args[1], args[2])
            elif args[0] == "scan":
                # Это результат сканирования
                self._on_scan_complete(args[1], args[2], args[3])
            elif isinstance(args[0], bool):
                # Это результат подключения
                self._on_connect_complete(args[0], args[1])
        elif len(args) == 4 and args[0] == "scan_progress":
            # Это прогресс сканирования
            self._on_scan_progress(args[1], args[2], args[3])

    def _on_async_error(self, error):
        """Обработка ошибки асинхронной задачи"""
        self.debug_log(f"_on_async_error: {error}", "ERROR")
        messagebox.showerror("Асинхронная ошибка", f"Ошибка: {error}")

    def setup_mouse_wheel_scroll(self):
        """Настройка прокрутки колесиком мыши для всех виджетов"""
        # Привязываем прокрутку колесиком к основному окну
        self.root.bind("<MouseWheel>", self._on_mousewheel)

        # Для Linux (Button-4 и Button-5 для прокрутки)
        self.root.bind("<Button-4>", lambda e: self._on_mousewheel_linux(e, -1))
        self.root.bind("<Button-5>", lambda e: self._on_mousewheel_linux(e, 1))

    def _on_mousewheel(self, event):
        """Обработка прокрутки колесиком мыши (Windows/Mac)"""
        # Прокрутка Treeview
        if hasattr(self, 'files_tree'):
            try:
                self.files_tree.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except:
                pass

        # Прокрутка текстового поля лога
        if hasattr(self, 'log_text'):
            try:
                self.log_text.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except:
                pass

        # Прокрутка текстового поля дебага
        if hasattr(self, 'debug_text'):
            try:
                self.debug_text.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except:
                pass

    def _on_mousewheel_linux(self, event, direction):
        """Обработка прокрутки колесиком мыши (Linux)"""
        # Прокрутка Treeview
        if hasattr(self, 'files_tree'):
            try:
                self.files_tree.yview_scroll(direction, "units")
            except:
                pass

        # Прокрутка текстового поля лога
        if hasattr(self, 'log_text'):
            try:
                self.log_text.yview_scroll(direction, "units")
            except:
                pass

        # Прокрутка текстового поля дебага
        if hasattr(self, 'debug_text'):
            try:
                self.debug_text.yview_scroll(direction, "units")
            except:
                pass

    def setup_ui(self):
        """Настройка пользовательского интерфейса"""
        style = ttk.Style()
        style.theme_use('clam')

        # Основной контейнер
        main_container = ttk.Frame(self.root)
        main_container.pack(fill='both', expand=True, padx=5, pady=5)

        # Панель вкладок
        self.notebook = ttk.Notebook(main_container)
        self.notebook.pack(fill='both', expand=True)

        # Создание вкладок
        self.setup_connection_tab()
        self.setup_extensions_tab()
        self.setup_files_tab()
        self.setup_download_tab()
        self.setup_debug_tab()  # Новая вкладка дебага

        # Статус бар
        self.setup_status_bar()

    def setup_connection_tab(self):
        """Вкладка подключения - БЕЗ ПРОКРУТКИ"""
        self.conn_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.conn_frame, text="🔐 Подключение")

        # Создаем основной фрейм с прокруткой (но без видимого скроллбара)
        main_frame = ttk.Frame(self.conn_frame)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Внутренний фрейм для содержимого
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill='both', expand=True, padx=5, pady=5)

        # Заголовок
        ttk.Label(content_frame, text="Настройки Telegram API",
                  font=('Arial', 14, 'bold')).pack(pady=(10, 20))

        # Фрейм для формы
        form_frame = ttk.LabelFrame(content_frame, text="Данные для подключения", padding=15)
        form_frame.pack(fill='x', pady=10)

        # Ссылка на получение API
        link_frame = ttk.Frame(form_frame)
        link_frame.pack(fill='x', pady=(0, 10))
        ttk.Label(link_frame, text="Получить API на:").pack(side='left')
        link = ttk.Label(link_frame, text="my.telegram.org",
                         foreground='blue', cursor='hand2')
        link.pack(side='left', padx=5)
        link.bind('<Button-1>', lambda e: webbrowser.open("https://my.telegram.org"))

        # Поля ввода - делаем компактнее
        fields = [
            ("API ID:", "api_id_var", True),
            ("API Hash:", "api_hash_var", True),
            ("Номер телефона:", "phone_var", True),
            ("Пароль 2FA (если есть):", "password_var", False),
        ]

        self.entries = []  # Список для хранения ссылок на поля ввода

        for i, (label, var_name, required) in enumerate(fields):
            frame = ttk.Frame(form_frame)
            frame.pack(fill='x', pady=3)  # Уменьшаем отступы

            ttk.Label(frame, text=label, width=18).pack(side='left')

            var = tk.StringVar()
            setattr(self, var_name, var)

            if "api_hash" in var_name or "password" in var_name:
                entry = ttk.Entry(frame, textvariable=var, width=30, show="•")
                entry.pack(side='left', fill='x', expand=True, padx=5)

                show_btn = ttk.Checkbutton(frame, text="👁", width=3,
                                           command=lambda e=entry: self.toggle_password_visibility(e))
                show_btn.pack(side='right')
            else:
                entry = ttk.Entry(frame, textvariable=var, width=35)
                entry.pack(side='left', fill='x', expand=True, padx=5)

            # Добавляем поддержку вставки через контекстное меню
            self.setup_context_menu(entry)
            self.entries.append(entry)

            if required:
                ttk.Label(frame, text="*", foreground='red').pack(side='right')

        # Кнопки подключения
        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(fill='x', pady=10)

        self.connect_btn = ttk.Button(btn_frame, text="Подключиться",
                                      command=self.connect_to_telegram)
        self.connect_btn.pack(side='left', padx=5)

        self.disconnect_btn = ttk.Button(btn_frame, text="Отключиться",
                                         command=self.disconnect_from_telegram,
                                         state='disabled')
        self.disconnect_btn.pack(side='left', padx=5)

        # Кнопка для вставки тестовых данных (только для отладки)
        if __name__ == "__main__":
            ttk.Button(btn_frame, text="Тест данные",
                       command=self.fill_test_data).pack(side='left', padx=5)

        # Статус подключения
        self.connection_status = ttk.Label(form_frame, text="❌ Не подключено",
                                           foreground='red')
        self.connection_status.pack(pady=5)

        # Фрейм для чата
        chat_frame = ttk.LabelFrame(content_frame, text="Информация о чате", padding=10)
        chat_frame.pack(fill='x', pady=10)

        ttk.Label(chat_frame, text="Ссылка на чат/канал:").pack(anchor='w')

        input_frame = ttk.Frame(chat_frame)
        input_frame.pack(fill='x', pady=5)

        self.chat_link_var = tk.StringVar()
        self.chat_entry = ttk.Entry(input_frame, textvariable=self.chat_link_var, width=40)
        self.chat_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))

        # Добавляем поддержку вставки для поля чата
        self.setup_context_menu(self.chat_entry)

        self.load_chat_btn = ttk.Button(input_frame, text="Загрузить информацию",
                                        command=self.load_chat_info,
                                        state='disabled')
        self.load_chat_btn.pack(side='right')

        # Информация о чате
        self.chat_info_label = ttk.Label(chat_frame, text="Чат не загружен")
        self.chat_info_label.pack(anchor='w', pady=5)

        # Предварительная оценка размера
        self.size_preview_label = ttk.Label(chat_frame, text="")
        self.size_preview_label.pack(anchor='w')

    def setup_context_menu(self, widget):
        """Настройка контекстного меню для виджета"""
        # Создаем меню
        menu = tk.Menu(widget, tearoff=0)
        menu.add_command(label="Вырезать", command=lambda: self.cut_text(widget))
        menu.add_command(label="Копировать", command=lambda: self.copy_text(widget))
        menu.add_command(label="Вставить", command=lambda: self.paste_text(widget))
        menu.add_separator()
        menu.add_command(label="Выбрать все", command=lambda: self.select_all_text(widget))

        # Привязываем меню к правой кнопке мыши
        if isinstance(widget, tk.Text) or isinstance(widget, scrolledtext.ScrolledText):
            widget.bind("<Button-3>", lambda e: self.show_context_menu(e, menu))
        else:
            widget.bind("<Button-3>", lambda e: self.show_context_menu(e, menu))

        # Также добавляем стандартные горячие клавиши
        widget.bind("<Control-a>", lambda e: self.select_all_text(widget))
        widget.bind("<Control-c>", lambda e: self.copy_text(widget))
        widget.bind("<Control-x>", lambda e: self.cut_text(widget))
        widget.bind("<Control-v>", lambda e: self.paste_text(widget))

    def show_context_menu(self, event, menu):
        """Показать контекстное меню"""
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def cut_text(self, widget):
        """Вырезать текст"""
        try:
            if isinstance(widget, tk.Text) or isinstance(widget, scrolledtext.ScrolledText):
                widget.event_generate("<<Cut>>")
            else:
                # Для Entry виджетов
                widget.event_generate("<<Cut>>")
        except:
            pass

    def copy_text(self, widget):
        """Копировать текст"""
        try:
            if isinstance(widget, tk.Text) or isinstance(widget, scrolledtext.ScrolledText):
                widget.event_generate("<<Copy>>")
            else:
                # Для Entry виджетов
                widget.event_generate("<<Copy>>")
        except:
            pass

    def paste_text(self, widget):
        """Вставить текст"""
        try:
            if isinstance(widget, tk.Text) or isinstance(widget, scrolledtext.ScrolledText):
                widget.event_generate("<<Paste>>")
            else:
                # Для Entry виджетов
                widget.event_generate("<<Paste>>")
        except:
            pass

    def select_all_text(self, widget):
        """Выбрать весь текст"""
        try:
            if isinstance(widget, tk.Text) or isinstance(widget, scrolledtext.ScrolledText):
                widget.tag_add(tk.SEL, "1.0", tk.END)
                widget.mark_set(tk.INSERT, "1.0")
                widget.see(tk.INSERT)
                return 'break'
            else:
                # Для Entry виджетов
                widget.select_range(0, tk.END)
                return 'break'
        except:
            pass

    def fill_test_data(self):
        """Заполнить тестовые данные (только для отладки)"""
        # Это только для тестирования! Не используйте реальные данные
        self.api_id_var.set("123456")
        self.api_hash_var.set("abc123def456")
        self.phone_var.set("+1234567890")
        self.debug_log("Заполнены тестовые данные")
        messagebox.showinfo("Тест", "Заполнены тестовые данные для отладки")

    def setup_extensions_tab(self):
        """Вкладка выбора расширений С ПРОКРУТКОЙ"""
        self.ext_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.ext_frame, text="📁 Типы файлов")

        # Создаем Canvas и Scrollbar для прокрутки
        canvas = tk.Canvas(self.ext_frame)
        scrollbar = ttk.Scrollbar(self.ext_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Упаковываем canvas и scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Создаем селектор расширений
        self.extension_selector.create_widgets(scrollable_frame)

        # Кнопка сохранения настроек
        btn_frame = ttk.Frame(scrollable_frame)
        btn_frame.pack(fill='x', pady=15, padx=20)

        ttk.Button(btn_frame, text="Сохранить выбор",
                   command=self.save_extension_settings).pack(side='left', padx=5)

        # Показать выбранные расширения
        self.selected_ext_label = ttk.Label(btn_frame, text="Выбрано: 0 расширений")
        self.selected_ext_label.pack(side='right', padx=5)

    def setup_files_tab(self):
        """Вкладка списка файлов"""
        self.files_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.files_frame, text="📋 Список файлов")

        # Верхняя панель
        top_frame = ttk.Frame(self.files_frame)
        top_frame.pack(fill='x', padx=20, pady=10)

        # Кнопки управления
        btn_frame = ttk.Frame(top_frame)
        btn_frame.pack(side='left')

        self.scan_btn = ttk.Button(btn_frame, text="🔍 Сканировать файлы",
                                   command=self.scan_files, state='disabled')
        self.scan_btn.pack(side='left', padx=5)

        self.stop_scan_btn = ttk.Button(btn_frame, text="⏹️ Остановить",
                                        command=self.stop_scanning, state='disabled')
        self.stop_scan_btn.pack(side='left', padx=5)

        # Прогресс сканирования
        scan_progress_frame = ttk.Frame(top_frame)
        scan_progress_frame.pack(side='left', padx=20)

        self.scan_progress_label = ttk.Label(scan_progress_frame, text="")
        self.scan_progress_label.pack()

        # Статистика
        stats_frame = ttk.Frame(top_frame)
        stats_frame.pack(side='right')

        self.total_files_label = ttk.Label(stats_frame, text="Всего файлов: 0")
        self.total_files_label.pack(side='left', padx=10)

        self.total_size_label = ttk.Label(stats_frame, text="Общий размер: 0 MB")
        self.total_size_label.pack(side='left', padx=10)

        self.selected_count_label = ttk.Label(stats_frame, text="Выбрано: 0")
        self.selected_count_label.pack(side='left', padx=10)

        # Панель поиска и фильтров
        filter_frame = ttk.LabelFrame(self.files_frame, text="Фильтры и поиск", padding=10)
        filter_frame.pack(fill='x', padx=20, pady=10)

        # Поиск по имени
        search_frame = ttk.Frame(filter_frame)
        search_frame.pack(fill='x', pady=5)

        ttk.Label(search_frame, text="Поиск:").pack(side='left')
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=40)
        self.search_entry.pack(side='left', padx=10, fill='x', expand=True)
        self.search_entry.bind('<KeyRelease>', lambda e: self.filter_files())

        # Добавляем поддержку вставки для поля поиска
        self.setup_context_menu(self.search_entry)

        # Фильтр по категориям
        category_frame = ttk.Frame(filter_frame)
        category_frame.pack(fill='x', pady=5)

        ttk.Label(category_frame, text="Категория:").pack(side='left')
        self.category_var = tk.StringVar(value="Все")
        categories = ["Все"] + list(ALL_EXTENSIONS.keys())
        self.category_combo = ttk.Combobox(category_frame, textvariable=self.category_var,
                                           values=categories, width=15)
        self.category_combo.pack(side='left', padx=10)
        self.category_combo.bind('<<ComboboxSelected>>', lambda e: self.filter_files())

        # Таблица файлов с двойной прокруткой
        table_frame = ttk.Frame(self.files_frame)
        table_frame.pack(fill='both', expand=True, padx=20, pady=10)

        # Создаем Treeview с прокруткой
        columns = ('Выбор', 'Имя файла', 'Размер', 'Тип', 'Категория', 'Дата')
        self.files_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)

        # Настройка колонок
        self.files_tree.heading('Выбор', text='Выбор')
        self.files_tree.heading('Имя файла', text='Имя файла')
        self.files_tree.heading('Размер', text='Размер')
        self.files_tree.heading('Тип', text='Тип')
        self.files_tree.heading('Категория', text='Категория')
        self.files_tree.heading('Дата', text='Дата')

        self.files_tree.column('Выбор', width=50, anchor='center')
        self.files_tree.column('Имя файла', width=300)
        self.files_tree.column('Размер', width=100, anchor='center')
        self.files_tree.column('Тип', width=80, anchor='center')
        self.files_tree.column('Категория', width=100, anchor='center')
        self.files_tree.column('Дата', width=120, anchor='center')

        # Добавляем вертикальную и горизонтальную прокрутку
        y_scrollbar = ttk.Scrollbar(table_frame, orient='vertical', command=self.files_tree.yview)
        x_scrollbar = ttk.Scrollbar(table_frame, orient='horizontal', command=self.files_tree.xview)
        self.files_tree.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)

        # Используем grid для правильного расположения
        self.files_tree.grid(row=0, column=0, sticky='nsew')
        y_scrollbar.grid(row=0, column=1, sticky='ns')
        x_scrollbar.grid(row=1, column=0, sticky='ew')

        # Настраиваем вес строк и столбцов
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        # Кнопки выбора файлов
        select_frame = ttk.Frame(self.files_frame)
        select_frame.pack(fill='x', padx=20, pady=10)

        ttk.Button(select_frame, text="Выбрать все",
                   command=self.select_all_files).pack(side='left', padx=5)
        ttk.Button(select_frame, text="Снять выделение",
                   command=self.deselect_all_files).pack(side='left', padx=5)
        ttk.Button(select_frame, text="Инвертировать выбор",
                   command=self.invert_selection).pack(side='left', padx=5)

        # Подсветка выбранных файлов
        self.files_tree.tag_configure('selected', background='#e0f7fa')

    def setup_download_tab(self):
        """Вкладка загрузки"""
        self.download_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.download_frame, text="⬇️ Загрузка")

        # Настройки загрузки
        settings_frame = ttk.LabelFrame(self.download_frame, text="Настройки загрузки", padding=15)
        settings_frame.pack(fill='x', padx=20, pady=10)

        # Путь сохранения
        path_frame = ttk.Frame(settings_frame)
        path_frame.pack(fill='x', pady=5)

        ttk.Label(path_frame, text="Путь сохранения:").pack(side='left')
        self.download_path_var = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "Downloads"))
        self.path_entry = ttk.Entry(path_frame, textvariable=self.download_path_var, width=40)
        self.path_entry.pack(side='left', padx=10, fill='x', expand=True)

        # Добавляем поддержку вставки для поля пути
        self.setup_context_menu(self.path_entry)

        ttk.Button(path_frame, text="Обзор",
                   command=self.browse_download_path).pack(side='right')

        # Префикс файлов
        prefix_frame = ttk.Frame(settings_frame)
        prefix_frame.pack(fill='x', pady=5)

        ttk.Label(prefix_frame, text="Префикс файлов:").pack(side='left')
        self.file_prefix_var = tk.StringVar()
        self.prefix_entry = ttk.Entry(prefix_frame, textvariable=self.file_prefix_var, width=20)
        self.prefix_entry.pack(side='left', padx=10)

        # Добавляем поддержку вставки для поля префикса
        self.setup_context_menu(self.prefix_entry)

        ttk.Label(prefix_frame, text="(добавляется в начало имени файла)").pack(side='left')

        # Создание подпапок
        self.create_subfolders_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(settings_frame, text="Создавать подпапки по категориям",
                        variable=self.create_subfolders_var).pack(anchor='w', pady=5)

        self.overwrite_files_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(settings_frame, text="Перезаписывать существующие файлы",
                        variable=self.overwrite_files_var).pack(anchor='w', pady=5)

        # Информация о загрузке
        info_frame = ttk.LabelFrame(self.download_frame, text="Информация о загрузке", padding=15)
        info_frame.pack(fill='x', padx=20, pady=10)

        self.download_info_label = ttk.Label(info_frame, text="Выбрано файлов: 0")
        self.download_info_label.pack(anchor='w')

        self.download_size_label = ttk.Label(info_frame, text="Общий размер: 0 MB")
        self.download_size_label.pack(anchor='w')

        # Прогресс бар
        progress_frame = ttk.Frame(self.download_frame)
        progress_frame.pack(fill='x', padx=20, pady=10)

        ttk.Label(progress_frame, text="Прогресс загрузки:").pack(anchor='w')
        self.progress_bar = ttk.Progressbar(progress_frame, length=400, mode='determinate')
        self.progress_bar.pack(fill='x', pady=5)

        self.progress_label = ttk.Label(progress_frame, text="0% (0/0)")
        self.progress_label.pack()

        # Лог загрузки
        log_frame = ttk.LabelFrame(self.download_frame, text="Лог загрузки", padding=10)
        log_frame.pack(fill='both', expand=True, padx=20, pady=10)

        # Используем ScrolledText для автоматической прокрутки
        self.log_text = scrolledtext.ScrolledText(log_frame, height=8, width=80, wrap=tk.WORD)
        self.log_text.pack(fill='both', expand=True)

        # Добавляем поддержку вставки для лога
        self.setup_context_menu(self.log_text)

        # Кнопки управления загрузкой
        button_frame = ttk.Frame(self.download_frame)
        button_frame.pack(fill='x', padx=20, pady=10)

        self.start_download_btn = ttk.Button(button_frame, text="Начать загрузку",
                                             command=self.start_download,
                                             state='disabled')
        self.start_download_btn.pack(side='left', padx=5)

        self.pause_download_btn = ttk.Button(button_frame, text="Приостановить",
                                             command=self.pause_download,
                                             state='disabled')
        self.pause_download_btn.pack(side='left', padx=5)

        self.cancel_download_btn = ttk.Button(button_frame, text="Отменить",
                                              command=self.cancel_download,
                                              state='disabled')
        self.cancel_download_btn.pack(side='left', padx=5)

        # Кнопка открытия папки
        ttk.Button(button_frame, text="Открыть папку загрузки",
                   command=self.open_download_folder).pack(side='right', padx=5)

    def setup_debug_tab(self):
        """Вкладка дебага"""
        self.debug_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.debug_frame, text="🐞 Дебаг")

        # Верхняя панель управления
        control_frame = ttk.Frame(self.debug_frame)
        control_frame.pack(fill='x', padx=20, pady=10)

        ttk.Button(control_frame, text="Очистить логи",
                   command=self.clear_debug_log).pack(side='left', padx=5)
        ttk.Button(control_frame, text="Экспорт в файл",
                   command=self.export_debug_log).pack(side='left', padx=5)
        ttk.Button(control_frame, text="Тестовое сообщение",
                   command=self.test_debug_message).pack(side='left', padx=5)

        # Панель фильтров
        filter_frame = ttk.LabelFrame(self.debug_frame, text="Фильтры", padding=10)
        filter_frame.pack(fill='x', padx=20, pady=10)

        filter_row = ttk.Frame(filter_frame)
        filter_row.pack(fill='x')

        ttk.Label(filter_row, text="Уровень логирования:").pack(side='left', padx=5)

        self.debug_level_var = tk.StringVar(value="ALL")
        levels = ["ALL", "INFO", "WARNING", "ERROR", "TRACEBACK"]
        self.debug_level_combo = ttk.Combobox(filter_row, textvariable=self.debug_level_var,
                                              values=levels, width=15, state="readonly")
        self.debug_level_combo.pack(side='left', padx=5)

        self.debug_auto_scroll_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(filter_row, text="Автопрокрутка",
                        variable=self.debug_auto_scroll_var).pack(side='left', padx=20)

        # Текстовое поле для логов
        log_frame = ttk.Frame(self.debug_frame)
        log_frame.pack(fill='both', expand=True, padx=20, pady=10)

        # Используем ScrolledText для прокрутки
        self.debug_text = scrolledtext.ScrolledText(log_frame, height=15, width=80, wrap=tk.WORD)
        self.debug_text.pack(fill='both', expand=True)

        # Добавляем поддержку вставки для дебаг текста
        self.setup_context_menu(self.debug_text)

        # Настраиваем цвета для разных уровней логирования
        self.debug_text.tag_config("INFO", foreground="black")
        self.debug_text.tag_config("WARNING", foreground="orange")
        self.debug_text.tag_config("ERROR", foreground="red")
        self.debug_text.tag_config("TRACEBACK", foreground="purple")

        # Статусная строка дебага
        self.debug_status_label = ttk.Label(self.debug_frame, text="Готов к записи логов")
        self.debug_status_label.pack(padx=20, pady=5, anchor='w')

    def setup_status_bar(self):
        """Создание статус бара"""
        self.status_bar = ttk.Frame(self.root, relief='sunken', padding=(5, 2))
        self.status_bar.pack(side='bottom', fill='x')

        self.status_label = ttk.Label(self.status_bar, text="Готов")
        self.status_label.pack(side='left')

        # Индикатор подключения
        self.connection_indicator = tk.Canvas(self.status_bar, width=20, height=20)
        self.connection_indicator.pack(side='right')
        self.draw_connection_indicator(False)

    # ========== МЕТОДЫ ДЛЯ РАБОТЫ С TELEGRAM ==========

    def connect_to_telegram(self):
        """Подключение к Telegram"""
        self.debug_log("Начало подключения к Telegram")

        api_id = self.api_id_var.get().strip()
        api_hash = self.api_hash_var.get().strip()
        phone = self.phone_var.get().strip()
        password = self.password_var.get().strip() or None

        if not api_id or not api_hash or not phone:
            error_msg = "Заполните обязательные поля: API ID, API Hash и номер телефона"
            self.debug_log(error_msg, "ERROR")
            messagebox.showerror("Ошибка", error_msg)
            return

        try:
            api_id = int(api_id)
        except ValueError:
            error_msg = "API ID должен быть числом"
            self.debug_log(error_msg, "ERROR")
            messagebox.showerror("Ошибка", error_msg)
            return

        # Блокируем кнопку подключения
        self.connect_btn.config(state='disabled')
        self.connection_status.config(text="⏳ Подключаюсь...", foreground='orange')

        # Сохраняем API данные для создания клиента
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.password = password

        # Запускаем асинхронную задачу
        self.run_async_task(self._async_connect)

    async def _async_connect(self):
        """Асинхронное подключение"""
        # Создаем клиента
        self.client.create_client(self.api_id, self.api_hash)

        async def code_callback():
            self.debug_log("Запрос кода подтверждения от пользователя")
            return self.get_code_from_user()

        success, message = await self.client.connect(
            self.phone,
            self.password,
            code_callback
        )

        return success, message

    def _on_connect_complete(self, success, message):
        """Обработка завершения подключения"""
        self.debug_log(f"Результат подключения: success={success}, message={message}")

        if success:
            self.is_connected = True
            self.connection_status.config(text="✅ Подключено", foreground='green')
            self.load_chat_btn.config(state='normal')
            self.disconnect_btn.config(state='normal')
            self.draw_connection_indicator(True)
            messagebox.showinfo("Успех", message)
        else:
            self.connection_status.config(text="❌ Ошибка подключения", foreground='red')
            messagebox.showerror("Ошибка", message)

        self.connect_btn.config(state='normal')

    def get_code_from_user(self):
        """Получение кода подтверждения от пользователя"""
        self.debug_log("Открытие диалога для ввода кода подтверждения")

        # Создаем диалоговое окно для ввода кода
        dialog = tk.Toplevel(self.root)
        dialog.title("Ввод кода подтверждения")
        dialog.geometry("300x150")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Введите код из Telegram:",
                  font=('Arial', 11)).pack(pady=20)

        code_var = tk.StringVar()
        entry = ttk.Entry(dialog, textvariable=code_var, width=20, font=('Arial', 12))
        entry.pack(pady=10)

        # Добавляем поддержку вставки для диалогового окна
        self.setup_context_menu(entry)

        result = {"code": None}

        def on_ok():
            result["code"] = code_var.get()
            self.debug_log(f"Пользователь ввёл код: {'*' * len(result['code'])}")
            dialog.destroy()

        def on_cancel():
            self.debug_log("Пользователь отменил ввод кода")
            dialog.destroy()

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)

        ttk.Button(btn_frame, text="OK", command=on_ok).pack(side='left', padx=10)
        ttk.Button(btn_frame, text="Отмена", command=on_cancel).pack(side='left', padx=10)

        entry.focus()
        dialog.wait_window()

        return result["code"]

    def disconnect_from_telegram(self):
        """Отключение от Telegram"""
        self.debug_log("Отключение от Telegram")

        if self.client.is_connected:
            # Здесь нужно реализовать отключение
            self.is_connected = False
            self.client.is_connected = False
            self.connection_status.config(text="❌ Не подключено", foreground='red')
            self.load_chat_btn.config(state='disabled')
            self.disconnect_btn.config(state='disabled')
            self.scan_btn.config(state='disabled')
            self.draw_connection_indicator(False)
            messagebox.showinfo("Информация", "Отключено от Telegram")

    def draw_connection_indicator(self, connected):
        """Рисует индикатор подключения"""
        self.connection_indicator.delete("all")
        color = "green" if connected else "red"
        self.connection_indicator.create_oval(2, 2, 18, 18, fill=color, outline="")

    def load_chat_info(self):
        """Загрузка информации о чате"""
        self.debug_log(f"Загрузка информации о чате: {self.chat_link_var.get()}")

        chat_link = self.chat_link_var.get().strip()
        if not chat_link:
            error_msg = "Введите ссылку на чат или канал"
            self.debug_log(error_msg, "ERROR")
            messagebox.showerror("Ошибка", error_msg)
            return

        # Обновляем статус
        self.status_label.config(text="Загружаю информацию о чате...")
        self.load_chat_btn.config(state='disabled')

        # Запускаем асинхронную задачу
        self.run_async_task(self._async_load_chat, chat_link)

    async def _async_load_chat(self, chat_link):
        """Асинхронная загрузка информации о чате"""
        success, result = await self.client.get_chat_info(chat_link)

        if success:
            self.current_chat = result
            chat_name = getattr(result, 'title', getattr(result, 'username', 'Неизвестно'))
            return "success", chat_name
        else:
            return "error", result

    def _on_chat_load_success(self, chat_name):
        """Обработка успешной загрузки чата"""
        self.debug_log(f"Чат успешно загружен: {chat_name}")

        self.chat_info_label.config(text=f"✅ Чат: {chat_name}")
        self.scan_btn.config(state='normal')
        self.load_chat_btn.config(state='normal')
        self.status_label.config(text="Готов")

        # Запрашиваем предварительную оценку размера
        self.estimate_size()

    def _on_chat_load_error(self, error):
        """Обработка ошибки загрузки чата"""
        self.debug_log(f"Ошибка загрузки чата: {error}", "ERROR")

        messagebox.showerror("Ошибка", error)
        self.load_chat_btn.config(state='normal')
        self.status_label.config(text="Ошибка загрузки чата")

    def estimate_size(self):
        """Предварительная оценка размера файлов"""
        self.debug_log("Начало оценки размера файлов")

        if not self.current_chat:
            return

        # Обновляем статус
        self.size_preview_label.config(text="⏳ Оцениваю общий размер...")

        # Запускаем асинхронную задачу
        self.run_async_task(self._async_estimate_size)

    async def _async_estimate_size(self):
        """Асинхронная оценка размера"""
        selected_extensions = self.extension_selector.get_selected_extensions()
        files, total_size = await self.client.get_all_files(
            self.current_chat,
            limit=100,
            selected_extensions=selected_extensions
        )

        total_mb = total_size / (1024 * 1024)
        file_count = len(files)

        return "estimate", file_count, total_mb

    def _on_estimate_complete(self, file_count, total_mb):
        """Обработка завершения оценки размера"""
        self.debug_log(f"Оценка размера завершена: {file_count} файлов, {total_mb:.2f} MB")

        if file_count > 0:
            self.size_preview_label.config(
                text=f"📊 Примерно {file_count} файлов ({total_mb:.1f} MB)"
            )
        else:
            self.size_preview_label.config(
                text="📊 Файлы выбранных типов не найдены"
            )

    def scan_files(self):
        """Сканирование файлов в чате"""
        self.debug_log("Начало сканирования файлов")

        if not self.current_chat:
            error_msg = "Сначала загрузите чат"
            self.debug_log(error_msg, "ERROR")
            messagebox.showerror("Ошибка", error_msg)
            return

        # Получаем выбранные расширения
        selected_extensions = self.extension_selector.get_selected_extensions()
        if not selected_extensions:
            self.debug_log("Расширения не выбраны, запрос подтверждения у пользователя")
            if not messagebox.askyesno("Подтверждение",
                                       "Вы не выбрали ни одного расширения. Сканировать все типы файлов?"):
                return

        # Обновляем интерфейс
        self.is_scanning = True
        self.scan_btn.config(state='disabled')
        self.stop_scan_btn.config(state='normal')
        self.status_label.config(text="Сканирую файлы...")
        self.scan_progress_label.config(text="Обработано: 0 сообщений")

        # Очищаем список файлов
        self.all_files = []
        self.files_tree.delete(*self.files_tree.get_children())

        # Запускаем асинхронную задачу
        self.run_async_task(self._async_scan_files, selected_extensions)

    async def _async_scan_files(self, selected_extensions):
        """Асинхронное сканирование файлов"""

        async def progress_callback(processed_count):
            # Отправляем промежуточные результаты
            if processed_count % 100 == 0:
                self.root.after(0, self._on_scan_progress, "scan_progress", processed_count, len(self.all_files), 0)

        files, total_size = await self.client.get_all_files(
            self.current_chat,
            limit=25000,
            selected_extensions=selected_extensions,
            progress_callback=progress_callback
        )

        self.all_files = files
        total_mb = total_size / (1024 * 1024)

        return "scan", files, len(files), total_mb

    def _on_scan_progress(self, processed_count, found_files, total_mb):
        """Обработка прогресса сканирования"""
        self.scan_progress_label.config(text=f"Обработано: {processed_count} сообщений, найдено: {found_files} файлов")

    def _on_scan_complete(self, files, file_count, total_mb):
        """Обработка завершения сканирования"""
        self.debug_log(f"Сканирование завершено: найдено {file_count} файлов, {total_mb:.2f} MB")

        self.is_scanning = False
        self.scan_btn.config(state='normal')
        self.stop_scan_btn.config(state='disabled')
        self.scan_progress_label.config(text="")
        self.status_label.config(text="Сканирование завершено")

        # Обновляем статистику
        self.total_files_label.config(text=f"Всего файлов: {file_count}")
        self.total_size_label.config(text=f"Общий размер: {total_mb:.1f} MB")

        # Заполняем таблицу файлами
        for file in files:
            size_mb = file.size_bytes / (1024 * 1024)
            date_str = file.date.strftime("%Y-%m-%d %H:%M")

            # Сокращаем длинные имена файлов
            display_name = file.filename
            if len(display_name) > 50:
                display_name = display_name[:47] + "..."

            item_id = self.files_tree.insert("", "end", values=(
                "☐",
                display_name,
                f"{size_mb:.1f} MB",
                file.extension,
                file.category,
                date_str
            ), tags=(str(file.id),))

        self._update_selection_count()

    def stop_scanning(self):
        """Остановка сканирования"""
        self.debug_log("Остановка сканирования файлов")

        self.is_scanning = False
        self.client.is_connected = False  # Это прервет цикл сканирования
        self.status_label.config(text="Сканирование остановлено")
        self.scan_btn.config(state='normal')
        self.stop_scan_btn.config(state='disabled')

        # Восстанавливаем соединение
        self.client.is_connected = True

    # ========== МЕТОДЫ ДЛЯ РАБОТЫ С ФАЙЛАМИ ==========

    def select_all_files(self):
        """Выбрать все файлы в таблице"""
        self.debug_log("Выбор всех файлов")

        for item in self.files_tree.get_children():
            self.files_tree.set(item, 'Выбор', '☑')
            self.files_tree.item(item, tags=('selected',))
        self._update_selection_count()

    def deselect_all_files(self):
        """Снять выбор со всех файлов"""
        self.debug_log("Снятие выбора со всех файлов")

        for item in self.files_tree.get_children():
            self.files_tree.set(item, 'Выбор', '☐')
            self.files_tree.item(item, tags=())
        self._update_selection_count()

    def invert_selection(self):
        """Инвертировать выбор файлов"""
        self.debug_log("Инвертирование выбора файлов")

        for item in self.files_tree.get_children():
            current = self.files_tree.set(item, 'Выбор')
            new = '☑' if current == '☐' else '☐'
            self.files_tree.set(item, 'Выбор', new)

            if new == '☑':
                self.files_tree.item(item, tags=('selected',))
            else:
                self.files_tree.item(item, tags=())

        self._update_selection_count()

    def _update_selection_count(self):
        """Обновить счетчик выбранных файлов"""
        selected = 0
        total_size = 0

        for item in self.files_tree.get_children():
            if self.files_tree.set(item, 'Выбор') == '☑':
                selected += 1
                # Получаем размер из таблицы
                size_str = self.files_tree.set(item, 'Размер')
                if 'MB' in size_str:
                    try:
                        size_mb = float(size_str.replace(' MB', ''))
                        total_size += size_mb
                    except:
                        pass

        self.selected_count_label.config(text=f"Выбрано: {selected}")

        # Обновляем информацию в вкладке загрузки
        self.download_info_label.config(text=f"Выбрано файлов: {selected}")
        self.download_size_label.config(text=f"Общий размер: {total_size:.1f} MB")

        # Активируем кнопку загрузки если есть выбранные файлы
        if selected > 0:
            self.start_download_btn.config(state='normal')
        else:
            self.start_download_btn.config(state='disabled')

    def filter_files(self):
        """Фильтрация файлов по поиску и категории"""
        search_text = self.search_var.get().lower()
        selected_category = self.category_var.get()

        for item in self.files_tree.get_children():
            filename = self.files_tree.set(item, 'Имя файла').lower()
            category = self.files_tree.set(item, 'Категория')

            match_search = not search_text or search_text in filename
            match_category = selected_category == "Все" or category == selected_category

            if match_search and match_category:
                self.files_tree.attached(item)
            else:
                self.files_tree.detach(item)

    # ========== МЕТОДЫ ДЛЯ ЗАГРУЗКИ ==========

    def browse_download_path(self):
        """Выбор папки для загрузки"""
        self.debug_log("Выбор папки для загрузки")

        folder = filedialog.askdirectory(
            title="Выберите папку для загрузки",
            initialdir=self.download_path_var.get()
        )
        if folder:
            self.download_path_var.set(folder)
            self.debug_log(f"Выбрана папка: {folder}")

    def start_download(self):
        """Начало загрузки файлов"""
        self.debug_log("Начало загрузки файлов")

        # Получаем выбранные файлы
        selected_files = []
        for item in self.files_tree.get_children():
            if self.files_tree.set(item, 'Выбор') == '☑':
                file_id = int(self.files_tree.item(item, 'tags')[0])
                filename = self.files_tree.set(item, 'Имя файла').split('...')[0]  # Убираем ...
                selected_files.append({'id': file_id, 'filename': filename})

        if not selected_files:
            error_msg = "Выберите файлы для загрузки"
            self.debug_log(error_msg, "ERROR")
            messagebox.showerror("Ошибка", error_msg)
            return

        # Проверяем папку для загрузки
        download_path = self.download_path_var.get()
        if not download_path or not os.path.exists(download_path):
            error_msg = "Выберите корректную папку для загрузки"
            self.debug_log(error_msg, "ERROR")
            messagebox.showerror("Ошибка", error_msg)
            return

        # Подтверждение перед загрузкой
        total_size = 0
        for item in self.files_tree.get_children():
            if self.files_tree.set(item, 'Выбор') == '☑':
                size_str = self.files_tree.set(item, 'Размер')
                if 'MB' in size_str:
                    try:
                        total_size += float(size_str.replace(' MB', ''))
                    except:
                        pass

        confirm = messagebox.askyesno(
            "Подтверждение",
            f"Начать загрузку {len(selected_files)} файлов?\n"
            f"Общий размер: {total_size:.1f} MB\n\n"
            f"Папка: {download_path}\n"
            f"Префикс: {self.file_prefix_var.get() or 'Нет'}"
        )

        if not confirm:
            self.debug_log("Пользователь отменил загрузку")
            return

        # Обновляем интерфейс
        self.is_downloading = True
        self.start_download_btn.config(state='disabled')
        self.pause_download_btn.config(state='normal')
        self.cancel_download_btn.config(state='normal')
        self.progress_bar['value'] = 0
        self.progress_label.config(text="0% (0/0)")
        self.log_text.delete(1.0, tk.END)
        self.log_text.insert(tk.END, "Начинаю загрузку...\n")

        # Запускаем загрузку в отдельном потоке
        self.run_async_task(self._async_download_files, selected_files, download_path)

    async def _async_download_files(self, selected_files, download_path):
        """Асинхронная загрузка файлов"""
        prefix = self.file_prefix_var.get()
        create_subfolders = self.create_subfolders_var.get()
        overwrite = self.overwrite_files_var.get()

        total_files = len(selected_files)
        downloaded = 0

        self.debug_log(f"Начало загрузки {total_files} файлов в {download_path}")

        for i, file_info in enumerate(selected_files):
            if not self.is_downloading:
                self.debug_log("Загрузка прервана пользователем")
                break

            try:
                # Получаем информацию о расширении файла из списка
                extension = None
                for file in self.all_files:
                    if file.id == file_info['id']:
                        extension = file.extension
                        break

                # Создаем имя файла с префиксом
                filename = f"{prefix}{file_info['filename']}" if prefix else file_info['filename']

                # Определяем путь для сохранения
                if create_subfolders and extension:
                    category = EXTENSION_CATEGORIES.get(extension, 'Другие')
                    category_path = os.path.join(download_path, category)
                    os.makedirs(category_path, exist_ok=True)
                    file_path = os.path.join(category_path, filename)
                else:
                    file_path = os.path.join(download_path, filename)

                # Проверяем существование файла
                if os.path.exists(file_path) and not overwrite:
                    # Добавляем номер к имени файла
                    base, ext = os.path.splitext(file_path)
                    counter = 1
                    while os.path.exists(f"{base}_{counter}{ext}"):
                        counter += 1
                    file_path = f"{base}_{counter}{ext}"

                # Скачиваем файл
                success, error = await self.client.download_file(self.current_chat, file_info['id'], file_path)

                if success:
                    downloaded += 1
                    log_msg = f"✅ Скачан: {os.path.basename(file_path)}\n"
                    self.root.after(0, self._add_log_message, log_msg)
                    self.debug_log(f"Файл скачан: {os.path.basename(file_path)}")
                else:
                    log_msg = f"❌ Ошибка при загрузке {filename}: {error}\n"
                    self.root.after(0, self._add_log_message, log_msg)
                    self.debug_log(f"Ошибка загрузки файла {filename}: {error}", "ERROR")

                # Обновляем прогресс
                progress = (i + 1) / total_files * 100
                self.root.after(0, self._update_progress, progress, i + 1, total_files)

                # Небольшая задержка чтобы не перегружать сервер
                await asyncio.sleep(0.5)

            except Exception as e:
                log_msg = f"❌ Ошибка при загрузке {file_info['filename']}: {str(e)}\n"
                self.root.after(0, self._add_log_message, log_msg)
                self.debug_log(f"Исключение при загрузке файла {file_info['filename']}: {str(e)}", "ERROR")

        # Завершаем загрузку
        self.root.after(0, self._on_download_complete, downloaded, total_files)

    def _update_progress(self, progress, current, total):
        """Обновление прогресса загрузки"""
        self.progress_bar['value'] = progress
        self.progress_label.config(text=f"{progress:.1f}% ({current}/{total})")

    def _add_log_message(self, message):
        """Добавление сообщения в лог"""
        self.log_text.insert(tk.END, message)
        self.log_text.see(tk.END)

    def _on_download_complete(self, downloaded, total):
        """Обработка завершения загрузки"""
        self.debug_log(f"Загрузка завершена: {downloaded} из {total} файлов")

        self.is_downloading = False
        self.start_download_btn.config(state='normal')
        self.pause_download_btn.config(state='disabled')
        self.cancel_download_btn.config(state='disabled')

        message = f"Загрузка завершена!\nСкачано: {downloaded} из {total} файлов"
        self.log_text.insert(tk.END, f"\n{message}\n")
        self.status_label.config(text="Загрузка завершена")

        messagebox.showinfo("Успех", message)

    def _on_download_error(self, error):
        """Обработка ошибки загрузки"""
        self.debug_log(f"Ошибка загрузки: {error}", "ERROR")

        self.is_downloading = False
        self.start_download_btn.config(state='normal')
        self.pause_download_btn.config(state='disabled')
        self.cancel_download_btn.config(state='disabled')

        self.log_text.insert(tk.END, f"\n❌ Ошибка загрузки: {error}\n")
        self.status_label.config(text="Ошибка загрузки")

        messagebox.showerror("Ошибка", f"Ошибка при загрузке: {error}")

    def pause_download(self):
        """Приостановка загрузки"""
        self.debug_log("Приостановка загрузки")

        self.is_downloading = False
        self.pause_download_btn.config(state='disabled')
        self.start_download_btn.config(state='normal')
        self.log_text.insert(tk.END, "⏸️ Загрузка приостановлена\n")
        self.status_label.config(text="Загрузка приостановлена")

    def cancel_download(self):
        """Отмена загрузки"""
        self.debug_log("Отмена загрузки")

        self.is_downloading = False
        self.start_download_btn.config(state='normal')
        self.pause_download_btn.config(state='disabled')
        self.cancel_download_btn.config(state='disabled')
        self.log_text.insert(tk.END, "⏹️ Загрузка отменена\n")
        self.status_label.config(text="Загрузка отменена")

    def open_download_folder(self):
        """Открытие папки загрузки"""
        path = self.download_path_var.get()
        if os.path.exists(path):
            self.debug_log(f"Открытие папки: {path}")

            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                os.system(f"open '{path}'")
            else:
                os.system(f"xdg-open '{path}'")
        else:
            self.debug_log(f"Папка не существует: {path}", "ERROR")

    # ========== МЕТОДЫ ДЛЯ РАБОТЫ С НАСТРОЙКАМИ ==========

    def save_extension_settings(self):
        """Сохранение настроек расширений"""
        selected = self.extension_selector.get_selected_extensions()
        self.settings['extensions'] = list(selected)
        self._save_settings()

        count = len(selected)
        self.selected_ext_label.config(text=f"Выбрано: {count} расширений")
        messagebox.showinfo("Сохранено", f"Сохранено {count} расширений")

        self.debug_log(f"Сохранены настройки расширений: {count} расширений")

    def save_settings(self):
        """Сохранение всех настроек"""
        self.settings['api_id'] = self.api_id_var.get()
        self.settings['api_hash'] = self.api_hash_var.get()
        self.settings['phone'] = self.phone_var.get()
        self.settings['download_path'] = self.download_path_var.get()

        self._save_settings()
        messagebox.showinfo("Сохранено", "Настройки сохранены")

        self.debug_log("Сохранены все настройки")

    def _save_settings(self):
        """Сохранение настроек в файл"""
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
        except Exception as e:
            error_msg = f"Ошибка сохранения настроек: {e}"
            self.debug_log(error_msg, "ERROR")
            print(error_msg)

    def load_settings(self):
        """Загрузка настроек из файла"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    self.settings = json.load(f)

                # Загружаем настройки в поля
                self.api_id_var.set(self.settings.get('api_id', ''))
                self.api_hash_var.set(self.settings.get('api_hash', ''))
                self.phone_var.set(self.settings.get('phone', ''))
                self.download_path_var.set(self.settings.get('download_path',
                                                             os.path.join(os.path.expanduser("~"), "Downloads")))

                # Загружаем расширения
                if 'extensions' in self.settings:
                    self.extension_selector.load_settings(self.settings['extensions'])
                    count = len(self.settings['extensions'])
                    self.selected_ext_label.config(text=f"Выбрано: {count} расширений")

                self.debug_log(f"Настройки загружены из {self.settings_file}")
        except Exception as e:
            error_msg = f"Ошибка загрузки настроек: {e}"
            self.debug_log(error_msg, "ERROR")
            self.settings = {}

    def toggle_password_visibility(self, entry):
        """Переключение видимости пароля"""
        if entry.cget('show') == '•':
            entry.config(show='')
        else:
            entry.config(show='•')

    # ========== МЕТОДЫ ДЛЯ РАБОТЫ С ДЕБАГОМ ==========

    def clear_debug_log(self):
        """Очистка логов дебага"""
        self.debug_text.delete(1.0, tk.END)
        self.debug_status_label.config(text="Логи очищены")
        self.debug_log("Логи дебага очищены")

    def export_debug_log(self):
        """Экспорт логов дебага в файл"""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"debug_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )

        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.debug_text.get(1.0, tk.END))
                self.debug_log(f"Логи экспортированы в файл: {file_path}")
                self.debug_status_label.config(text=f"Логи экспортированы в {os.path.basename(file_path)}")
            except Exception as e:
                error_msg = f"Ошибка экспорта логов: {e}"
                self.debug_log(error_msg, "ERROR")
                messagebox.showerror("Ошибка", error_msg)

    def test_debug_message(self):
        """Тестовое сообщение для проверки работы дебага"""
        self.debug_log("Тестовое информационное сообщение")
        self.debug_log("Тестовое предупреждение", "WARNING")
        self.debug_log("Тестовая ошибка", "ERROR")
        self.debug_log("Тестовый traceback", "TRACEBACK")

        # Добавляем тестовый traceback
        try:
            raise ValueError("Тестовое исключение")
        except Exception as e:
            self.debug_log(f"Поймано исключение: {e}", "TRACEBACK")
            self.debug_log(traceback.format_exc(), "TRACEBACK")


def main():
    """Основная функция"""
    root = tk.Tk()
    app = TelegramDownloaderGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
