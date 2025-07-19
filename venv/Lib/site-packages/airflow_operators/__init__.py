import inspect
import os
import sys


def get_importer_path():
    """
    Получает путь к файлу, который импортировал текущий модуль.
    Используется для определения корневого каталога проекта,
    чтобы даги могли импортировать модули из других каталогов.
    """
    stack = inspect.stack()
    for frame_info in stack[1:]:  # Пропускаем текущий фрейм
        frame = frame_info.frame
        module_name = frame.f_globals.get('__name__', '')
        file_path = frame.f_globals.get('__file__', '')

        # Пропускаем служебные модули Python
        if (
                not file_path  # Нет файла (например, REPL или exec)
                or module_name.startswith('importlib')
                or 'frozen importlib' in file_path
                or file_path.startswith('<')  # Например, <stdin>
                or file_path.startswith(os.path.dirname(os.path.realpath(__file__)))
        ):
            continue

        # Нормализуем путь
        abs_path = os.path.abspath(file_path)
        return os.path.dirname(abs_path)

    return None  # Не удалось определить


def ensure_path():
    # Получаем путь
    importer_dir = get_importer_path()

    # Добавляем в sys.path (если найден и ещё не добавлен)
    if importer_dir and importer_dir not in sys.path:
        sys.path.insert(0, importer_dir)

    print('ensure_path', importer_dir)
