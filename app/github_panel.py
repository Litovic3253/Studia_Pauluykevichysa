"""Кнопки и окна синхронизации с GitHub: выгрузка, скачивание, настройка, выбор версии при расхождении.
Сама синхронизация — в app/github_sync.py; здесь только то, что видит пользователь."""
import logging
import threading
from typing import Callable

import flet as ft

from app import github_sync, theme

TOKEN_HELP = ("Токен создаётся на github.com: Settings → Developer settings → Fine-grained tokens. "
              "Доступ — только к репозиторию с данными, право Contents: Read and write.")
CONFLICT_TEXT = (
    "И на этом компьютере, и в GitHub есть изменения, которых нет на другой стороне. "
    "Объединить их автоматически нельзя — выберите, какие данные оставить.\n\n"
    "Скачать из GitHub — здешние данные заменятся, прежняя база сохранится рядом с программой "
    "как orders.backup-<дата>.db.\n\n"
    "Выгрузить мои — данные в GitHub заменятся здешними, прежняя версия останется в истории репозитория."
)


class GithubPanel:
    """Живёт всё время работы приложения. on_downloaded — обновить экраны после замены базы."""

    def __init__(self, page: ft.Page, on_downloaded: Callable[[], None]):
        self.page = page
        self.on_downloaded = on_downloaded
        self._spawn: Callable[[Callable[[], None]], None] = (
            lambda work: threading.Thread(target=work, daemon=True).start())  # сеть — не в потоке интерфейса
        self._auto_error_shown = False
        self._conflict_open = False

        self.repo_field = ft.TextField(label="Репозиторий с данными", hint_text="владелец/название или ссылка",
                                       border_radius=theme.FIELD_RADIUS, **theme.FIELD_BORDER)
        self.token_field = ft.TextField(label="Токен GitHub", password=True, can_reveal_password=True,
                                        border_radius=theme.FIELD_RADIUS, **theme.FIELD_BORDER)
        self.error_text = ft.Text("", size=12, color=theme.ERR)
        self.save_button = ft.FilledButton("Сохранить", on_click=lambda e: self.save_settings())
        self.settings_dialog = ft.AlertDialog(
            title=ft.Text("Настройка GitHub"),
            content=ft.Container(ft.Column([
                ft.Text("Заказы, клиенты, цены и вложения хранятся в вашем приватном репозитории: "
                        "выгружаются сами после каждого изменения и скачиваются на другом компьютере.",
                        size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                self.repo_field, self.token_field,
                ft.Text(TOKEN_HELP, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                self.error_text,
            ], spacing=14, tight=True), width=460),
            actions=[ft.TextButton("Отмена", on_click=lambda e: page.close(self.settings_dialog)),
                     self.save_button],
        )
        self.conflict_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Данные различаются"),
            content=ft.Container(ft.Text(CONFLICT_TEXT, size=13), width=460),
            actions=[ft.TextButton("Позже", on_click=lambda e: self.resolve_conflict("later")),
                     ft.OutlinedButton("Выгрузить мои", icon=ft.Icons.CLOUD_UPLOAD_OUTLINED,
                                       on_click=lambda e: self.resolve_conflict("upload")),
                     ft.OutlinedButton("Скачать из GitHub", icon=ft.Icons.CLOUD_DOWNLOAD_OUTLINED,
                                       on_click=lambda e: self.resolve_conflict("download"))],
        )

    # ---------- настройка ----------

    def open_settings(self) -> None:
        saved = github_sync.is_configured()
        self.repo_field.value = github_sync.current_repo()
        self.token_field.value = ""
        self.token_field.helper_text = "Уже сохранён — оставьте пустым, чтобы не менять." if saved else None
        self.error_text.value = ""
        self.save_button.disabled = False
        self.page.open(self.settings_dialog)

    def save_settings(self) -> None:
        repo, token = self.repo_field.value or "", self.token_field.value or ""
        self.error_text.value, self.error_text.color = "Проверяю доступ…", ft.Colors.ON_SURFACE_VARIANT
        self.save_button.disabled = True
        self.settings_dialog.update()

        def work() -> None:
            try:
                github_sync.save_config(repo, token)
            except github_sync.GithubSyncError as exc:
                self.error_text.value, self.error_text.color = str(exc), theme.ERR
                self.save_button.disabled = False
                self.settings_dialog.update()
                return
            self.page.close(self.settings_dialog)
            self._notify("GitHub подключён.")
            self.check_on_start()

        self._spawn(work)

    # ---------- кнопки ----------

    def upload(self, force: bool = False) -> None:
        if not github_sync.is_configured():
            self.open_settings()
            return
        self._spawn(lambda: self._run(
            lambda: github_sync.push(force=force),
            {"uploaded": "Данные выгружены в GitHub.", "unchanged": "В GitHub уже лежат эти данные."}))

    def download(self, force: bool = False) -> None:
        if not github_sync.is_configured():
            self.open_settings()
            return
        self._spawn(lambda: self._run(
            lambda: github_sync.pull(force=force),
            {"downloaded": "Данные скачаны из GitHub.", "unchanged": "Новых данных в GitHub нет."}))

    def _run(self, action: Callable[[], str], messages: dict[str, str]) -> None:
        try:
            result = action()
        except github_sync.ConflictError:
            self._ask_conflict()
            return
        except Exception as exc:  # noqa: BLE001 - любая ошибка сети или файла должна дойти до пользователя
            self._notify(f"GitHub: {exc}", error=True)
            return
        if result == "downloaded":
            self.on_downloaded()
        self._notify(messages[result])

    # ---------- автоматика ----------

    def auto_upload(self) -> None:
        """После изменения данных: выгрузка в фоне, без сообщений об успехе."""
        github_sync.push_in_background(on_done=self._auto_done, on_error=self._auto_error)

    def _auto_done(self, result: str) -> None:
        self._auto_error_shown = False

    def _auto_error(self, exc: Exception) -> None:
        if isinstance(exc, github_sync.ConflictError):
            self._ask_conflict()
        elif not self._auto_error_shown:  # без интернета не повторяем одно и то же после каждой правки
            self._auto_error_shown = True
            self._notify(f"Автовыгрузка в GitHub не удалась: {exc}", error=True)

    def check_on_start(self) -> None:
        """При запуске: предлагает скачать, если в GitHub данные новее; довыгружает, если новее здесь."""
        if not github_sync.is_configured():
            return

        def work() -> None:
            try:
                state = github_sync.status()
            except github_sync.GithubSyncError as exc:
                logging.warning("Проверка GitHub при запуске не удалась: %s", exc)
                return
            if state == "remote_newer":
                self.page.open(ft.SnackBar(ft.Text("В GitHub есть более новые данные."), action="Скачать",
                                           on_action=lambda e: self.download(), duration=20000))
            elif state == "conflict":
                self._ask_conflict()
            elif state == "local_newer":
                self.auto_upload()

        self._spawn(work)

    # ---------- расхождение ----------

    def _ask_conflict(self) -> None:
        if not self._conflict_open:  # окно модальное — закрывается только через resolve_conflict
            self._conflict_open = True
            self.page.open(self.conflict_dialog)

    def resolve_conflict(self, choice: str) -> None:
        self._conflict_open = False
        self.page.close(self.conflict_dialog)
        if choice == "download":
            self.download(force=True)
        elif choice == "upload":
            self.upload(force=True)

    def _notify(self, text: str, error: bool = False) -> None:
        self.page.open(ft.SnackBar(ft.Text(text), bgcolor=theme.ERR if error else None))
