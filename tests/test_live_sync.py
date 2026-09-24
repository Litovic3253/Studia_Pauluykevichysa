"""Тесты для фонового опроса БД (LiveSync)."""
import time

import db
from app.live_sync import LiveSync


def test_live_sync_calls_on_change_when_db_changes(temp_db):
    events = []
    sync = LiveSync(on_change=lambda: events.append(1), interval=0.05)
    sync.start()
    try:
        time.sleep(0.12)
        assert events == [], "не должно быть событий без изменений в БД"

        db.add_order({"client": "Тест", "contact": "", "cost": 0, "price": 0})
        time.sleep(0.2)
        assert events, "LiveSync должен был заметить новый заказ"
    finally:
        sync.stop()


def test_live_sync_stop_prevents_further_calls(temp_db):
    events = []
    sync = LiveSync(on_change=lambda: events.append(1), interval=0.05)
    sync.start()
    sync.stop()
    count_after_stop = len(events)
    db.add_order({"client": "Тест2", "contact": "", "cost": 0, "price": 0})
    time.sleep(0.15)
    assert len(events) == count_after_stop
