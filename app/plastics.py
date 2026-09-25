"""Справочник пластиков: доступ к встроенным данным, шкалы свойств и «быстрый выбор»."""
from app.plastics_data import FIELD_LABELS, PLASTICS, QUICK_CHOICE  # noqa: F401 - реэкспорт

# Словесная оценка из таблицы → шкала 0..5 (0 — неизвестно).
_LEVELS = {
    "низкая": 1, "средняя/низкая": 1.5, "средняя": 2, "средняя/высокая": 2.5,
    "высокая": 3, "хорошая": 3, "очень хорошая": 4, "очень высокая": 4, "экстремально высокая": 5,
}

# Свойства, которые показываются шкалами (ключ, подпись).
RATED_FIELDS = [("strength", "Прочность"), ("stiffness", "Жёсткость"), ("impact", "Ударостойкость"),
                ("heat", "Термостойкость"), ("moisture", "Влагостойкость")]

GROUPS = list(dict.fromkeys(p["group"] for p in PLASTICS))


def level(text: str) -> float:
    return _LEVELS.get((text or "").strip().lower(), 0)


def names() -> list[str]:
    return [p["name"] for p in PLASTICS]


def by_name(name: str) -> dict | None:
    return next((p for p in PLASTICS if p["name"] == name), None)


def matching(need: dict) -> list[str]:
    """Пластики для пункта «быстрого выбора». Токен без уточнения («PETG») означает семейство:
    PETG Basic и PETG HF, но не композит PETG-CF."""
    result = []
    for token in need["materials"]:
        for name in names():
            if (name == token or name.startswith(token + " ")) and name not in result:
                result.append(name)
    return result


def family(material: str | None) -> str:
    """«PLA», «PETG Basic», «PLA-CF» → «PLA», «PETG», «PLA» — чтобы подобрать катушки под материал заказа."""
    if not material:
        return ""
    return material.split()[0].split("-")[0].upper()
