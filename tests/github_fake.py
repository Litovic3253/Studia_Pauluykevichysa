"""Подмена GitHub для тестов синхронизации: репозиторий в памяти и переключение «компьютеров»."""
import base64
import json
from urllib.parse import unquote

import db
from app import github_sync


class FakeGithub:
    """Дерево файлов, чтение и запись через Contents API с проверкой sha — как у настоящего GitHub."""

    def __init__(self, private: bool = True):
        self.files: dict[str, bytes] = {}
        self.private = private
        self.offline = False
        self.puts: list[str] = []

    def request(self, method, path, body=None, raw=False, **_):
        if self.offline:
            raise github_sync.GithubSyncError("Нет связи с GitHub: тест")
        if path == "":
            return 200, json.dumps({"private": self.private}).encode()
        if path.startswith("/git/trees/HEAD"):
            if not self.files:
                return 409, b'{"message": "Git Repository is empty."}'
            tree = [{"path": p, "type": "blob", "sha": github_sync.blob_sha(d), "size": len(d)}
                    for p, d in self.files.items()]
            return 200, json.dumps({"tree": tree, "truncated": False}).encode()
        assert path.startswith("/contents/"), path
        name = unquote(path[len("/contents/"):])
        if method == "GET":
            if name not in self.files:
                return 404, b"{}"
            return 200, self.files[name]
        assert method == "PUT", method
        existing = self.files.get(name)
        if existing is not None and not body.get("sha"):
            return 422, b'{"message": "sha wasn\'t supplied"}'
        if (github_sync.blob_sha(existing) if existing is not None else None) != body.get("sha"):
            return 409, b'{"message": "does not match"}'
        self.files[name] = base64.b64decode(body["content"])
        self.puts.append(name)
        return 201, b"{}"


def use_pc(monkeypatch, folder) -> None:
    """Переключает «компьютер»: своя папка данных и своя база."""
    folder.mkdir(exist_ok=True)
    monkeypatch.setattr(github_sync, "_BASE_DIR", folder)
    monkeypatch.setattr(db, "DB_PATH", folder / "orders.db")
    db.init()


def add_order(client: str) -> int:
    return db.add_order({"client": client, "contact": "", "cost": 0, "price": 0})
