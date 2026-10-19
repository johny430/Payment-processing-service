import importlib
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2]


def import_all_models() -> None:
    """Импорт всех моделей из src/<домен>/models, чтобы они попали в Base.metadata"""
    for path in sorted(SRC_DIR.glob('*/models/*.py')):
        if path.name == '__init__.py':
            continue
        module = '.'.join(path.relative_to(SRC_DIR.parent).with_suffix('').parts)
        importlib.import_module(module)
