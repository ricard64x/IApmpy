import json
import os
import threading
from flask import request, has_request_context

_thread_local = threading.local()

_locales_dir = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'locales')

# Load language registry
with open(os.path.join(_locales_dir, 'languages.json'), 'r', encoding='utf-8') as f:
    _languages = json.load(f)

# Load translation files
_translations = {}
for filename in os.listdir(_locales_dir):
    if filename.endswith('.json') and filename != 'languages.json':
        locale_name = filename[:-5]
        with open(os.path.join(_locales_dir, filename), 'r', encoding='utf-8') as f:
            _translations[locale_name] = json.load(f)


def _resolve_locale(value: str) -> str | None:
    """Accept exact locales and standard regional tags such as es-PY."""
    if not isinstance(value, str):
        return None
    name = value.strip().lower().replace('_', '-')
    if name in _translations:
        return name
    base = name.split('-', 1)[0]
    return base if base in _translations else None


def set_locale(locale: str):
    """Set locale for the current background thread."""
    _thread_local.locale = _resolve_locale(locale) or 'es'


def get_locale() -> str:
    if has_request_context():
        header = request.headers.get('Accept-Language', '')
        for entry in header.split(','):
            lang = entry.split(';', 1)[0]
            resolved = _resolve_locale(lang)
            if resolved:
                return resolved
        return 'es'
    return _resolve_locale(getattr(_thread_local, 'locale', 'es')) or 'es'


def t(key: str, **kwargs) -> str:
    locale = get_locale()
    messages = _translations.get(locale, _translations.get('es', {}))

    value = messages
    for part in key.split('.'):
        if isinstance(value, dict):
            value = value.get(part)
        else:
            value = None
            break

    if value is None:
        value = _translations.get('es', {})
        for part in key.split('.'):
            if isinstance(value, dict):
                value = value.get(part)
            else:
                value = None
                break

    if value is None:
        return key

    if kwargs:
        for k, v in kwargs.items():
            value = value.replace(f'{{{k}}}', str(v))

    return value


def get_language_instruction() -> str:
    locale = get_locale()
    lang_config = _languages.get(locale, _languages.get('es', {}))
    return lang_config.get('llmInstruction', 'Por favor, responde en español.')
