"""Синхронизация данных с приватным репозиторием GitHub: выгрузка и скачивание базы заказов,
вложений и подписи. Работает через GitHub API по HTTPS — git на компьютере не нужен.

В репозитории лежит снимок: orders.db, files_storage/<номер заказа>/…, signature.png.
Построчного слияния нет — побеждает версия целиком, поэтому перед любой перезаписью
проверяется, не ушли ли вперёд обе стороны сразу (ConflictError)."""
import base64
import hashlib
import json
import logging
import os
import platform
import re
import sqlite3
import tempfile
import threading
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Callable
from urllib.parse import quote

from dotenv import set_key

import db
from paths import DATA_DIR

_API = "https://api.github.com"
_TIMEOUT = 120
# Папка данных: там же .env, файл состояния, вложения и резервные копии базы.
_BASE_DIR = DATA_DIR
_STATE_NAME = "github_sync.json"
DB_NAME = "orders.db"
STORAGE_DIR = "files_storage"
SIGNATURE_NAME = "signature.png"
MAX_FILE_BYTES = 50 * 1024 * 1024  # вложения крупнее GitHub API принимает плохо — пропускаем

_op_lock = threading.RLock()  # выгрузка и скачивание не должны идти одновременно
_private_checked: set[str] = set()  # репозитории, приватность которых уже проверена в этом запуске
_state_lock = threading.Lock()
_pending = False
_running = False


class GithubSyncError(RuntimeError):
    pass


class ConflictError(GithubSyncError):
    """И здесь, и в GitHub есть изменения, которых нет на другой стороне."""


# ---------- настройка ----------

def current_repo() -> str:
    return os.getenv("GITHUB_DATA_REPO", "").strip()


def _token() -> str:
    return os.getenv("GITHUB_TOKEN", "").strip()


def is_configured() -> bool:
    return bool(current_repo()) and bool(_token())


def normalize_repo(text: str) -> str:
    """«владелец/репозиторий» из того, что вставил пользователь: годится и ссылка целиком."""
    repo = re.sub(r"^(https?://)?(www\.)?github\.com/", "", text.strip()).strip("/")
    repo = repo.removesuffix(".git")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise GithubSyncError("Укажите репозиторий как «владелец/название» или ссылкой с github.com.")
    return repo


def save_config(repo_text: str, token: str) -> None:
    """Проверяет доступ и приватность репозитория и записывает настройку в .env рядом с программой.
    Пустой токен — оставить прежний."""
    repo = normalize_repo(repo_text)
    token = token.strip() or _token()
    if not token:
        raise GithubSyncError("Вставьте токен GitHub.")
    _check_repo(repo, token)
    env_path = _BASE_DIR / ".env"
    env_path.touch(exist_ok=True)
    set_key(str(env_path), "GITHUB_DATA_REPO", repo)
    set_key(str(env_path), "GITHUB_TOKEN", token)
    os.environ["GITHUB_DATA_REPO"] = repo
    os.environ["GITHUB_TOKEN"] = token
    _private_checked.add(repo)


# ---------- GitHub API ----------

def _request(method: str, path: str, body: dict | None = None, raw: bool = False, *,
             repo: str | None = None, token: str | None = None) -> tuple[int, bytes]:
    """Запрос к API репозитория. Возвращает (код ответа, тело); бросает только при отсутствии связи."""
    request = urllib.request.Request(
        f"{_API}/repos/{repo or current_repo()}{path}",
        data=json.dumps(body).encode("utf-8") if body is not None else None,
        method=method,
        headers={
            "Authorization": f"Bearer {token or _token()}",
            "Accept": "application/vnd.github.raw" if raw else "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "Studia-Pauluykevichusa",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except OSError as exc:  # URLError, таймаут, обрыв — всё это «нет связи»
        raise GithubSyncError(f"Нет связи с GitHub: {exc}") from exc


def _error(status: int) -> GithubSyncError:
    messages = {
        401: "GitHub не принял токен — проверьте, что он скопирован целиком и не истёк.",
        403: "GitHub отказал в доступе — токену нужно право Contents: Read and write.",
        404: "Репозиторий не найден или у токена нет к нему доступа.",
    }
    return GithubSyncError(messages.get(status, f"GitHub ответил ошибкой {status}."))


def _check_repo(repo: str, token: str | None = None) -> None:
    status, payload = _request("GET", "", repo=repo, token=token)
    if status != 200:
        raise _error(status)
    if not json.loads(payload).get("private"):
        raise GithubSyncError(
            f"Репозиторий {repo} публичный — данные клиентов увидит кто угодно. "
            "Сделайте его приватным или укажите другой.")


def _ensure_ready() -> None:
    if not is_configured():
        raise GithubSyncError("GitHub не настроен — откройте «Настройка GitHub».")
    repo = current_repo()
    if repo not in _private_checked:
        _check_repo(repo)
        _private_checked.add(repo)


def _remote_tree() -> dict[str, str]:
    """Все файлы репозитория: путь → sha содержимого. Пустой репозиторий — пустой словарь."""
    status, payload = _request("GET", "/git/trees/HEAD?recursive=1")
    if status in (404, 409):  # так GitHub отвечает, пока в репозитории нет ни одного коммита
        return {}
    if status != 200:
        raise _error(status)
    return {item["path"]: item["sha"] for item in json.loads(payload).get("tree", []) if item["type"] == "blob"}


def _get(rel: str) -> bytes:
    status, payload = _request("GET", "/contents/" + quote(rel), raw=True)
    if status != 200:
        raise _error(status)
    return payload


def _put(rel: str, data: bytes, old_sha: str | None) -> None:
    body = {"message": f"{rel} с компьютера {platform.node()}",
            "content": base64.b64encode(data).decode("ascii")}
    if old_sha:
        body["sha"] = old_sha
    status, _ = _request("PUT", "/contents/" + quote(rel), body)
    if status in (409, 422):  # sha не совпал: файл в GitHub успели заменить
        raise ConflictError("Данные в GitHub изменились во время выгрузки.")
    if status not in (200, 201):
        raise _error(status)


# ---------- отпечатки и состояние ----------

def blob_sha(data: bytes) -> str:
    """sha содержимого файла в том виде, как его считает git (и отдаёт GitHub)."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def _file_sha(path: Path, rel: str, state: dict) -> str:
    """sha файла на диске; пока размер и время изменения те же, берётся из состояния без перечитывания."""
    stat = path.stat()
    cache = state.setdefault("files", {})
    cached = cache.get(rel)
    if cached and cached[0] == stat.st_size and cached[1] == stat.st_mtime_ns:
        return cached[2]
    digest = hashlib.sha1(b"blob %d\0" % stat.st_size)
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    cache[rel] = [stat.st_size, stat.st_mtime_ns, digest.hexdigest()]
    return cache[rel][2]


def _load_state() -> dict:
    try:
        return json.loads((_BASE_DIR / _STATE_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_state(state: dict) -> None:
    (_BASE_DIR / _STATE_NAME).write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")


def _local_sig() -> str:
    return hashlib.sha1(repr(db.change_fingerprint()).encode("utf-8")).hexdigest()


def _local_is_empty() -> bool:
    return not (db.count_orders()["all"] or db.list_customers() or db.list_spools(include_archived=True))


def _has_local_changes(state: dict) -> bool:
    """Есть ли на этом компьютере правки, которых нет в GitHub. Свежая пустая база правками не считается."""
    if state.get("local_sig") is None:
        return not _local_is_empty()
    return state["local_sig"] != _local_sig()


# ---------- база ----------

def _copy_db(source: Path, target: Path) -> None:
    """Копия базы средствами SQLite — корректна и при открытом приложении (режим WAL)."""
    src, dst = sqlite3.connect(source), sqlite3.connect(target)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def _snapshot() -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / DB_NAME
        _copy_db(db.DB_PATH, target)
        return target.read_bytes()


def _restore(data: bytes) -> None:
    """Заменяет локальную базу скачанной, оставляя прежнюю рядом как orders.backup-<дата>.db."""
    with tempfile.TemporaryDirectory() as tmp:
        incoming = Path(tmp) / DB_NAME
        incoming.write_bytes(data)
        try:
            conn = sqlite3.connect(incoming)
            try:
                valid = conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'orders'").fetchone()
            finally:
                conn.close()
        except sqlite3.DatabaseError as exc:
            raise GithubSyncError("Файл базы в GitHub повреждён — локальные данные не тронуты.") from exc
        if not valid:
            raise GithubSyncError("В GitHub лежит не база заказов — локальные данные не тронуты.")
        if Path(db.DB_PATH).exists():
            _copy_db(db.DB_PATH, _BASE_DIR / f"orders.backup-{datetime.now():%Y-%m-%d_%H-%M-%S}.db")
        _copy_db(incoming, db.DB_PATH)


# ---------- файлы ----------

def _local_files() -> dict[str, Path]:
    files: dict[str, Path] = {}
    storage = _BASE_DIR / STORAGE_DIR
    if storage.is_dir():
        for path in sorted(storage.rglob("*")):
            if path.is_file():
                files[f"{STORAGE_DIR}/{path.relative_to(storage).as_posix()}"] = path
    signature = _BASE_DIR / SIGNATURE_NAME
    if signature.is_file():
        files[SIGNATURE_NAME] = signature
    return files


def _upload_files(tree: dict[str, str], state: dict) -> int:
    uploaded = 0
    for rel, path in _local_files().items():
        if path.stat().st_size > MAX_FILE_BYTES:
            continue
        if tree.get(rel) == _file_sha(path, rel, state):
            continue
        _put(rel, path.read_bytes(), tree.get(rel))
        uploaded += 1
    return uploaded


def _download_files(tree: dict[str, str], state: dict) -> int:
    downloaded = 0
    base = _BASE_DIR.resolve()
    for rel, sha in tree.items():
        if rel != SIGNATURE_NAME and not rel.startswith(STORAGE_DIR + "/"):
            continue
        target = (base / rel).resolve()
        if not target.is_relative_to(base):
            continue
        if target.is_file() and _file_sha(target, rel, state) == sha:
            continue
        data = _get(rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        downloaded += 1
    return downloaded


# ---------- выгрузка и скачивание ----------

def status() -> str:
    """Кто впереди: in_sync, local_newer, remote_newer, conflict или remote_empty (в GitHub ещё ничего нет)."""
    with _op_lock:
        _ensure_ready()
        remote_sha = _remote_tree().get(DB_NAME)
        state = _load_state()
        if remote_sha is None:
            return "remote_empty" if _local_is_empty() else "local_newer"
        local_changed = _has_local_changes(state)
        if remote_sha != state.get("remote_sha"):
            return "conflict" if local_changed else "remote_newer"
        return "local_newer" if local_changed else "in_sync"


def push(force: bool = False) -> str:
    """Выгружает базу, вложения и подпись. Возвращает "uploaded" или "unchanged".
    Если в GitHub лежит версия новее той, что этот компьютер видел, — ConflictError;
    force=True перезаписывает её (прежняя остаётся в истории репозитория)."""
    with _op_lock:
        _ensure_ready()
        tree = _remote_tree()
        state = _load_state()
        remote_sha = tree.get(DB_NAME)
        if remote_sha is not None and remote_sha != state.get("remote_sha") and not force:
            raise ConflictError("В GitHub лежат более новые данные с другого компьютера.")
        sig = _local_sig()
        uploaded = _upload_files(tree, state)
        if force or remote_sha is None or sig != state.get("local_sig"):
            data = _snapshot()
            sha = blob_sha(data)
            if sha != remote_sha:
                _put(DB_NAME, data, remote_sha)
                uploaded += 1
            state["remote_sha"], state["local_sig"] = sha, sig
        _save_state(state)
        return "uploaded" if uploaded else "unchanged"


def pull(force: bool = False) -> str:
    """Скачивает данные из GitHub. Возвращает "downloaded" или "unchanged".
    Если здесь есть невыгруженные правки, а в GitHub версия новее, — ConflictError;
    force=True заменяет локальную базу (она сохраняется как orders.backup-<дата>.db)."""
    with _op_lock:
        _ensure_ready()
        tree = _remote_tree()
        state = _load_state()
        remote_sha = tree.get(DB_NAME)
        if remote_sha is None:
            raise GithubSyncError("В GitHub пока нет данных — сначала выгрузите их с другого компьютера.")
        if remote_sha == state.get("remote_sha") and not force:
            downloaded = _download_files(tree, state)
            _save_state(state)
            return "downloaded" if downloaded else "unchanged"
        if _has_local_changes(state) and not force:
            raise ConflictError("На этом компьютере есть изменения, которые ещё не выгружены.")
        data = _get(DB_NAME)
        _restore(data)
        db.init()  # база могла прийти от более старой версии программы — догоняем схему
        _download_files(tree, state)
        state["remote_sha"], state["local_sig"] = blob_sha(data), _local_sig()
        _save_state(state)
        return "downloaded"


def push_in_background(on_done: Callable[[str], None] | None = None,
                       on_error: Callable[[Exception], None] | None = None) -> None:
    """Запускает push() в отдельном потоке, если GitHub настроен; иначе ничего не делает.
    Как и синхронизация с Google Таблицами: одновременно идёт одна выгрузка, вызовы во время
    работы дают ровно один повтор по её окончании."""
    global _pending, _running
    if not is_configured():
        return
    with _state_lock:
        _pending = True
        if _running:
            return
        _running = True

    def _run() -> None:
        global _pending, _running
        while True:
            with _state_lock:
                if not _pending:
                    _running = False
                    return
                _pending = False
            try:
                result = push()
            except Exception as exc:  # noqa: BLE001 - поток не должен умереть с _running=True
                logging.warning("Выгрузка в GitHub не удалась: %s", exc)
                if on_error:
                    on_error(exc)
            else:
                if on_done:
                    on_done(result)

    threading.Thread(target=_run, daemon=True).start()
