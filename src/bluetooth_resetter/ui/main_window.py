from __future__ import annotations

import queue
import threading
import tkinter as tk
import webbrowser
from datetime import datetime
from tkinter import messagebox, ttk

from ..i18n.translations import SUPPORTED_LANGUAGES, translate
from ..services.app_paths import get_config_path, get_icon_path, get_log_path, get_powershell_script_path
from ..services.config_service import ConfigService
from ..services.logging_service import configure_logger
from ..services.powershell_runner import BluetoothFixRunner
from ..version import __version__


DONATION_URL = "https://www.paypal.com/donate/?hosted_button_id=ZABFRXC2P3JQN"


class BluetoothResetterApp:
    def __init__(self, is_elevated: bool) -> None:
        # Se marca al cerrar la ventana para evitar programar callbacks sobre un root destruido.
        self.is_shutting_down = False
        self.is_elevated = is_elevated
        self.event_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.run_in_progress = False
        self.geometry_save_job: str | None = None
        self.auto_close_job: str | None = None
        self.auto_close_remaining = 0

        self.config_service = ConfigService(get_config_path())
        self.config = self.config_service.load()
        self.language = self.config.language

        self.logger = configure_logger(get_log_path())
        self.runner = BluetoothFixRunner(get_powershell_script_path(), get_log_path())

        self.root = tk.Tk()
        self.root.title(f"{self.t('app_name')} {__version__}")
        self.root.minsize(920, 620)
        self.root.geometry(self.config.geometry)
        self.root.configure(bg="#ede7da")

        icon_path = get_icon_path()
        if icon_path.exists():
            try:
                self.root.iconbitmap(default=str(icon_path))
            except Exception:
                self.logger.warning("No se pudo aplicar el icono de la aplicación.")

        self.style = ttk.Style()
        self._build_styles()
        self._build_menu()
        self._build_layout()
        self._bind_events()
        self._load_initial_state()

        self.root.protocol("WM_DELETE_WINDOW", self.on_exit)
        self.root.after(120, self._process_queue)

        if not self.is_elevated:
            self.set_status("status_limited")
            self.append_log(self.t("status_limited"), level="WARNING")
            self.logger.warning("La aplicación se ejecuta sin elevación administrativa.")

        if self.config.auto_run:
            self.root.after(900, self.start_fix)

    def t(self, key: str, **kwargs: object) -> str:
        return translate(self.language, key, **kwargs)

    def _build_styles(self) -> None:
        self.style.theme_use("clam")
        self.style.configure("Root.TFrame", background="#ede7da")
        self.style.configure("Panel.TFrame", background="#fffaf0")
        self.style.configure("Hero.TFrame", background="#1f4d5c")
        self.style.configure("Status.TFrame", background="#16343f")
        self.style.configure("Accent.TButton", font=("Segoe UI", 11, "bold"), padding=(18, 10), background="#b85c38", foreground="#ffffff")
        self.style.map("Accent.TButton", background=[("active", "#d26b42")])
        self.style.configure("Secondary.TButton", font=("Segoe UI", 10, "bold"), padding=(16, 10), background="#d7c4a7", foreground="#1f1f1f")
        self.style.map("Secondary.TButton", background=[("active", "#e4d5bb")])
        self.style.configure("HeroTitle.TLabel", background="#1f4d5c", foreground="#fff8e8", font=("Segoe UI Semibold", 22))
        self.style.configure("HeroBody.TLabel", background="#1f4d5c", foreground="#d6e7eb", font=("Segoe UI", 10))
        self.style.configure("CardTitle.TLabel", background="#fffaf0", foreground="#1d2a33", font=("Segoe UI Semibold", 11))
        self.style.configure("Body.TLabel", background="#fffaf0", foreground="#1d2a33", font=("Segoe UI", 10))
        self.style.configure("Status.TLabel", background="#16343f", foreground="#f8f6ef", font=("Segoe UI", 9))
        self.style.configure("Badge.TLabel", background="#f2b84b", foreground="#1f1f1f", font=("Segoe UI", 9, "bold"), padding=(10, 4))
        self.style.configure("DangerBadge.TLabel", background="#b85c38", foreground="#ffffff", font=("Segoe UI", 9, "bold"), padding=(10, 4))
        self.style.configure("TCheckbutton", background="#fffaf0", foreground="#1d2a33", font=("Segoe UI", 10))
        self.style.configure("TProgressbar", troughcolor="#305968", background="#f2b84b", bordercolor="#305968", lightcolor="#f2b84b", darkcolor="#f2b84b")

    def _build_menu(self) -> None:
        self.menu_bar = tk.Menu(self.root)

        menu_meta = self._get_menu_metadata()

        self.file_menu = tk.Menu(self.menu_bar, tearoff=False)
        self.file_menu.add_command(
            label=self.t("menu_run"),
            accelerator=self.t("menu_run_accel"),
            underline=menu_meta["items"]["run"],
            command=self.start_fix,
        )
        self.file_menu.add_separator()
        self.file_menu.add_command(
            label=self.t("menu_exit"),
            accelerator=self.t("menu_exit_accel"),
            underline=menu_meta["items"]["exit"],
            command=self.on_exit,
        )
        self.menu_bar.add_cascade(
            label=self.t("menu_file"),
            menu=self.file_menu,
            underline=menu_meta["menus"]["file"],
        )

        self.language_menu = tk.Menu(self.menu_bar, tearoff=False)
        # El menu de idiomas se construye desde SUPPORTED_LANGUAGES para escalar sin duplicar codigo.
        language_key_map = {
            "es": "language_es",
            "en": "language_en",
            "pt": "language_pt",
        }
        for lang in SUPPORTED_LANGUAGES:
            self.language_menu.add_command(
                label=self.t(language_key_map.get(lang, "language_en")),
                underline=0,
                command=lambda selected_language=lang: self.change_language(selected_language),
            )
        self.menu_bar.add_cascade(
            label=self.t("menu_language"),
            menu=self.language_menu,
            underline=menu_meta["menus"]["language"],
        )

        self.help_menu = tk.Menu(self.menu_bar, tearoff=False)
        self.help_menu.add_command(
            label=self.t("menu_donate"),
            underline=menu_meta["items"]["donate"],
            command=self.open_donation,
        )
        self.help_menu.add_separator()
        self.help_menu.add_command(
            label=self.t("menu_about"),
            accelerator=self.t("menu_about_accel"),
            underline=menu_meta["items"]["about"],
            command=self.show_about,
        )
        self.menu_bar.add_cascade(
            label=self.t("menu_help"),
            menu=self.help_menu,
            underline=menu_meta["menus"]["help"],
        )

        self.root.config(menu=self.menu_bar)

    def _build_layout(self) -> None:
        self.container = ttk.Frame(self.root, style="Root.TFrame", padding=16)
        self.container.pack(fill="both", expand=True)

        self.hero = ttk.Frame(self.container, style="Hero.TFrame", padding=20)
        self.hero.pack(fill="x")

        hero_text = ttk.Frame(self.hero, style="Hero.TFrame")
        hero_text.pack(side="left", fill="x", expand=True)

        self.title_label = ttk.Label(hero_text, style="HeroTitle.TLabel")
        self.title_label.pack(anchor="w")

        self.subtitle_label = ttk.Label(hero_text, style="HeroBody.TLabel")
        self.subtitle_label.pack(anchor="w", pady=(6, 0))

        badge_wrap = ttk.Frame(self.hero, style="Hero.TFrame")
        badge_wrap.pack(side="right", anchor="ne")

        self.version_badge = ttk.Label(badge_wrap, style="Badge.TLabel")
        self.version_badge.pack(anchor="e")

        self.admin_badge = ttk.Label(badge_wrap, style="Badge.TLabel" if self.is_elevated else "DangerBadge.TLabel")
        self.admin_badge.pack(anchor="e", pady=(8, 0))

        self.controls_panel = ttk.Frame(self.container, style="Panel.TFrame", padding=18)
        self.controls_panel.pack(fill="x", pady=(16, 12))

        controls_top = ttk.Frame(self.controls_panel, style="Panel.TFrame")
        controls_top.pack(fill="x")

        left_actions = ttk.Frame(controls_top, style="Panel.TFrame")
        left_actions.pack(side="left", fill="x", expand=True)

        self.fix_button = ttk.Button(left_actions, style="Accent.TButton", command=self.start_fix)
        self.fix_button.pack(side="left")

        # Boton directo para donaciones con enlace externo.
        self.donate_button = ttk.Button(left_actions, style="Secondary.TButton", command=self.open_donation)
        self.donate_button.pack(side="left", padx=(10, 0))

        self.exit_button = ttk.Button(left_actions, style="Secondary.TButton", command=self.on_exit)
        self.exit_button.pack(side="left", padx=(10, 0))

        right_options = ttk.Frame(controls_top, style="Panel.TFrame")
        right_options.pack(side="right", anchor="e")

        self.auto_run_var = tk.BooleanVar(value=self.config.auto_run)
        self.auto_close_var = tk.BooleanVar(value=self.config.auto_close)
        self.auto_close_seconds_var = tk.StringVar(value=str(self.config.auto_close_seconds))

        self.auto_run_check = ttk.Checkbutton(right_options, variable=self.auto_run_var, command=self._on_option_change)
        self.auto_run_check.grid(row=0, column=0, sticky="w", padx=(0, 16))

        self.auto_close_check = ttk.Checkbutton(right_options, variable=self.auto_close_var, command=self._on_option_change)
        self.auto_close_check.grid(row=0, column=1, sticky="w", padx=(0, 16))

        self.seconds_label = ttk.Label(right_options, style="Body.TLabel")
        self.seconds_label.grid(row=0, column=2, sticky="e", padx=(0, 8))

        vcmd = (self.root.register(self._validate_seconds), "%P")
        self.seconds_spinbox = ttk.Spinbox(
            right_options,
            from_=5,
            to=3600,
            textvariable=self.auto_close_seconds_var,
            width=8,
            validate="key",
            validatecommand=vcmd,
        )
        self.seconds_spinbox.grid(row=0, column=3, sticky="e")

        hint_row = ttk.Frame(self.controls_panel, style="Panel.TFrame")
        hint_row.pack(fill="x", pady=(14, 0))

        self.device_hint_label = ttk.Label(hint_row, style="Body.TLabel")
        self.device_hint_label.pack(anchor="w")

        self.log_panel = ttk.Frame(self.container, style="Panel.TFrame", padding=18)
        self.log_panel.pack(fill="both", expand=True)

        self.log_title_label = ttk.Label(self.log_panel, style="CardTitle.TLabel")
        self.log_title_label.pack(anchor="w")

        text_wrap = ttk.Frame(self.log_panel, style="Panel.TFrame")
        text_wrap.pack(fill="both", expand=True, pady=(10, 0))

        self.log_text = tk.Text(
            text_wrap,
            wrap="word",
            font=("Cascadia Mono", 10),
            bg="#162127",
            fg="#f5f1e8",
            insertbackground="#f5f1e8",
            relief="flat",
            borderwidth=0,
            padx=14,
            pady=12,
        )
        self.log_text.pack(side="left", fill="both", expand=True)
        self.log_text.configure(state="disabled")

        scrollbar = ttk.Scrollbar(text_wrap, orient="vertical", command=self.log_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=scrollbar.set)

        self.status_bar = ttk.Frame(self.root, style="Status.TFrame", padding=(14, 8))
        self.status_bar.pack(fill="x", side="bottom")

        self.status_var = tk.StringVar()
        self.countdown_var = tk.StringVar()

        self.status_label = ttk.Label(self.status_bar, textvariable=self.status_var, style="Status.TLabel")
        self.status_label.pack(side="left")

        self.progress = ttk.Progressbar(self.status_bar, mode="indeterminate", length=150)
        self.progress.pack(side="right", padx=(12, 0))

        self.countdown_label = ttk.Label(self.status_bar, textvariable=self.countdown_var, style="Status.TLabel")
        self.countdown_label.pack(side="right")

    def _bind_events(self) -> None:
        self.root.bind_all("<Control-r>", lambda event: self.start_fix())
        self.root.bind_all("<Control-R>", lambda event: self.start_fix())
        self.root.bind_all("<Control-q>", lambda event: self.on_exit())
        self.root.bind_all("<Control-Q>", lambda event: self.on_exit())
        self.root.bind_all("<F1>", lambda event: self.show_about())
        self.root.bind("<Configure>", self._on_window_configure)
        self.auto_close_seconds_var.trace_add("write", self._on_seconds_changed)

    def _load_initial_state(self) -> None:
        self.refresh_texts()
        self.set_status("status_ready")
        self.countdown_var.set(self.t("status_idle_countdown"))
        self.append_log(self.t("status_ready"))

    def refresh_texts(self) -> None:
        self.root.title(f"{self.t('app_name')} {__version__}")
        self.title_label.configure(text=self.t("app_name"))
        self.subtitle_label.configure(text=self.t("subtitle"))
        self.version_badge.configure(text=self.t("version_label", version=__version__))
        self.admin_badge.configure(text=self.t("status_admin") if self.is_elevated else self.t("status_user"))
        self.fix_button.configure(text=self.t("fix_button"))
        self.donate_button.configure(text=self.t("donate_button"))
        self.exit_button.configure(text=self.t("exit_button"))
        self.auto_run_check.configure(text=self.t("auto_run"))
        self.auto_close_check.configure(text=self.t("auto_close"))
        self.seconds_label.configure(text=self.t("auto_close_seconds"))
        self.device_hint_label.configure(text=self.t("device_hint"))
        self.log_title_label.configure(text=self.t("log_title"))

        # Si hay countdown activo, se refresca de inmediato en el idioma seleccionado.
        if self.auto_close_job and self.auto_close_remaining > 0:
            self.countdown_var.set(self.t("status_countdown", seconds=self.auto_close_remaining))

        self._build_menu()

    def _get_menu_metadata(self) -> dict[str, dict[str, int]]:
        if self.language == "en":
            return {
                "menus": {
                    "file": 0,
                    "language": 0,
                    "help": 0,
                },
                "items": {
                    "run": 0,
                    "exit": 1,
                    "donate": 0,
                    "about": 0,
                },
            }

        return {
            "menus": {
                "file": 0,
                "language": 0,
                "help": 1,
            },
            "items": {
                "run": 0,
                "exit": 0,
                "donate": 0,
                "about": 0,
            },
        }

    def append_log(self, message: str, level: str = "INFO") -> None:
        if message.startswith("[") and "] [" in message:
            line = message
        else:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            line = f"[{timestamp}] [{level}] {message}"

        self.log_text.configure(state="normal")
        self.log_text.insert("end", line + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def set_status(self, key: str) -> None:
        self.status_var.set(self.t(key))

    def _validate_seconds(self, proposed: str) -> bool:
        return proposed == "" or (proposed.isdigit() and len(proposed) <= 4)

    def _on_option_change(self) -> None:
        self.config = self.config_service.update(
            auto_run=self.auto_run_var.get(),
            auto_close=self.auto_close_var.get(),
        )
        self.logger.info("Configuración actualizada: auto_run=%s auto_close=%s", self.config.auto_run, self.config.auto_close)

    def _on_seconds_changed(self, *_: object) -> None:
        value = self.auto_close_seconds_var.get().strip()
        if not value.isdigit():
            return

        self.config = self.config_service.update(auto_close_seconds=int(value))
        self.logger.info("Tiempo de autocierre actualizado a %s segundos.", self.config.auto_close_seconds)

    def _on_window_configure(self, _event: tk.Event) -> None:
        if self.root.state() != "normal":
            return

        if self.geometry_save_job:
            self.root.after_cancel(self.geometry_save_job)

        self.geometry_save_job = self.root.after(250, self._save_geometry)

    def _save_geometry(self) -> None:
        self.geometry_save_job = None
        self.config = self.config_service.update(geometry=self.root.geometry())

    def change_language(self, language: str) -> None:
        if language not in SUPPORTED_LANGUAGES:
            return

        self.language = language
        self.config = self.config_service.update(language=language)
        self.refresh_texts()

        if self.run_in_progress:
            self.set_status("status_running")
        elif not self.is_elevated:
            self.set_status("status_limited")
        else:
            self.set_status("status_ready")

    def start_fix(self) -> None:
        if self.run_in_progress:
            return

        self.cancel_auto_close(silent=True)
        self.run_in_progress = True
        self.fix_button.state(["disabled"])
        self.progress.start(10)
        self.set_status("status_running")
        self.append_log(self.t("launching_script"))
        self.logger.info("Se inició la reparación desde la GUI.")

        worker = threading.Thread(target=self._run_fix_worker, daemon=True)
        worker.start()

    def _run_fix_worker(self) -> None:
        try:
            return_code = self.runner.execute(lambda line: self.event_queue.put(("log", line)))
            self.event_queue.put(("done", return_code))
        except FileNotFoundError:
            self.event_queue.put(("error", self.t("script_missing")))
        except Exception as exc:
            self.logger.exception("Error inesperado durante la ejecución del backend.")
            self.event_queue.put(("error", str(exc)))

    def _process_queue(self) -> None:
        if self.is_shutting_down:
            return

        while True:
            try:
                event = self.event_queue.get_nowait()
            except queue.Empty:
                break

            event_type = event[0]

            if event_type == "log":
                self.append_log(str(event[1]))
            elif event_type == "done":
                self._finish_run(int(event[1]))
            elif event_type == "error":
                self._finish_run(1, str(event[1]))

        try:
            self.root.after(120, self._process_queue)
        except tk.TclError:
            # Si la ventana ya fue destruida, no se vuelve a programar el loop.
            return

    def open_donation(self) -> None:
        # Abre el enlace de PayPal de forma no bloqueante y registra el resultado.
        try:
            opened = webbrowser.open(DONATION_URL, new=2)
        except Exception as exc:
            self.append_log(f"{self.t('donate_open_error')} ({exc})", level="ERROR")
            self.logger.exception("No se pudo abrir el enlace de donacion.")
            messagebox.showerror(self.t("app_name"), self.t("donate_open_error"), parent=self.root)
            return

        if opened:
            self.append_log(self.t("donate_opened"))
        else:
            self.append_log(self.t("donate_open_error"), level="WARNING")

    def _finish_run(self, return_code: int, error_message: str | None = None) -> None:
        self.run_in_progress = False
        self.fix_button.state(["!disabled"])
        self.progress.stop()

        if error_message:
            self.append_log(error_message, level="ERROR")
            self.status_var.set(error_message)
            self.logger.error("La ejecución terminó con error: %s", error_message)
        elif return_code == 0:
            self.set_status("status_success")
            self.logger.info("La reparación terminó correctamente.")
        else:
            self.set_status("status_warning")
            self.logger.warning("La reparación terminó con código %s.", return_code)

        if self.config.auto_close:
            self.start_auto_close()

    def start_auto_close(self) -> None:
        self.auto_close_remaining = max(5, int(self.config.auto_close_seconds))
        self.logger.info("Autocierre programado en %s segundos.", self.auto_close_remaining)
        self._tick_auto_close()

    def _tick_auto_close(self) -> None:
        if self.auto_close_remaining <= 0:
            self.on_exit()
            return

        self.countdown_var.set(self.t("status_countdown", seconds=self.auto_close_remaining))
        self.auto_close_remaining -= 1
        self.auto_close_job = self.root.after(1000, self._tick_auto_close)

    def cancel_auto_close(self, silent: bool = False) -> None:
        if self.auto_close_job:
            self.root.after_cancel(self.auto_close_job)
            self.auto_close_job = None
        self.countdown_var.set(self.t("status_idle_countdown"))
        if not silent:
            self.logger.info("Autocierre cancelado.")

    def show_about(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title(self.t("about_title"))
        dialog.transient(self.root)
        dialog.resizable(False, False)
        dialog.configure(bg="#fffaf0")
        dialog.grab_set()

        container = ttk.Frame(dialog, style="Panel.TFrame", padding=20)
        container.pack(fill="both", expand=True)

        title = ttk.Label(container, text=self.t("app_name"), style="CardTitle.TLabel")
        title.pack(anchor="w")

        body = ttk.Label(
            container,
            text=self.t("about_body", name=self.t("app_name"), version=__version__, year=datetime.now().year),
            style="Body.TLabel",
            justify="left",
        )
        body.pack(anchor="w", pady=(10, 16))

        close_button = ttk.Button(container, text=self.t("about_close"), style="Secondary.TButton", command=dialog.destroy)
        close_button.pack(anchor="e")

    def on_exit(self) -> None:
        self.is_shutting_down = True
        self.cancel_auto_close(silent=True)

        # Guardado defensivo de geometria para evitar errores al salir durante eventos pendientes.
        try:
            self._save_geometry()
        except tk.TclError:
            pass

        self.logger.info("Aplicación cerrada por el usuario.")
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def run(self) -> None:
        self.root.mainloop()
