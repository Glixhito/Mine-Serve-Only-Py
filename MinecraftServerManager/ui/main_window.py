"""Ventana principal: barra lateral, topbar con breadcrumbs, páginas y barra de estado."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                               QMainWindow, QPushButton, QStackedWidget, QVBoxLayout, QWidget)

from ui.backup_scheduler import BackupScheduler
from ui.backups_view import BackupsView
from ui.dashboard import DashboardView
from ui.history_view import HistoryView
from ui.metrics_view import MetricsView
from ui.mod_view import ModView
from ui.players_view import PlayersView
from ui.presets_view import PresetsView
from ui.server_view import ServerView
from ui.settings_view import SettingsView
from ui.theme import GLOBAL_QSS
from ui.widgets.components import Badge
from ui.widgets.icons import svg_icon, svg_pixmap
from ui.zerotier_view import ZeroTierView

NAV_ITEMS = [
    ("Dashboard", "grid"),
    ("Servidores", "server"),
    ("Mods", "mods"),
    ("Jugadores", "users"),
    ("Respaldos", "archive"),
    ("Métricas", "activity"),
    ("ZeroTier", "network"),
    ("Rendimiento", "zap"),
    ("Ajustes", "settings"),
    ("Historial", "clock"),
]


class MainWindow(QMainWindow):
    def __init__(self, core) -> None:
        super().__init__()
        self._core = core
        self.setWindowTitle("Minecraft Server Manager")
        self.resize(1220, 760)
        self.setMinimumSize(960, 640)
        self.setStyleSheet(GLOBAL_QSS)

        # --- Sidebar izquierda ---
        sidebar = QFrame()
        sidebar.setFixedWidth(226)
        sidebar.setStyleSheet(
            "QFrame#Sidebar { background-color: #161920; border-right: 1px solid #2a2f3a; }"
        )
        sidebar.setObjectName("Sidebar")
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(12, 18, 12, 12)
        sb_layout.setSpacing(10)

        # Brand
        brand_row = QHBoxLayout()
        brand_row.setSpacing(10)
        brand_icon = QLabel()
        brand_icon.setPixmap(svg_pixmap("fox", 26, "#FF7A1A"))
        brand_icon.setStyleSheet("background: transparent;")
        brand_text = QVBoxLayout()
        brand_text.setSpacing(2)
        t1 = QLabel("Minecraft")
        t1.setStyleSheet("font-size: 16px; font-weight: 700; color: #f0f6fc; background: transparent;")
        t2 = QLabel("Server Manager  v1.0")
        t2.setStyleSheet("font-size: 11px; color: #8b949e; background: transparent;")
        brand_text.addWidget(t1)
        brand_text.addWidget(t2)
        brand_row.addWidget(brand_icon)
        brand_row.addLayout(brand_text, 1)
        sb_layout.addLayout(brand_row)

        # Workspace box
        ws = QFrame()
        ws.setStyleSheet(
            "QFrame { background-color: #191c23; border: 1px solid #2a2f3a; border-radius: 7px; }"
        )
        ws_row = QHBoxLayout(ws)
        ws_row.setContentsMargins(9, 8, 9, 8)
        ws_row.setSpacing(9)
        ws_ic = QLabel()
        ws_ic.setPixmap(svg_pixmap("monitor", 15, "#aeb6c1"))
        ws_ic.setStyleSheet("background: #242932; border: 1px solid #303540; border-radius: 5px; padding: 4px;")
        ws_col = QVBoxLayout()
        ws_col.setSpacing(1)
        ws_title = QLabel("Espacio local")
        ws_title.setStyleSheet("font-size: 11px; font-weight: 600; color: #f0f6fc; border: none; background: transparent;")
        ws_sub = QLabel("Tu equipo personal")
        ws_sub.setStyleSheet("font-size: 9px; color: #8b949e; border: none; background: transparent;")
        ws_col.addWidget(ws_title)
        ws_col.addWidget(ws_sub)
        ws_dot = QLabel("●")
        ws_dot.setStyleSheet("color: #3fb950; font-size: 8px; border: none; background: transparent;")
        ws_row.addWidget(ws_ic)
        ws_row.addLayout(ws_col, 1)
        ws_row.addWidget(ws_dot)
        sb_layout.addWidget(ws)

        cap_gen = QLabel("NAVEGACIÓN")
        cap_gen.setStyleSheet("color: #646d7a; font-size: 9px; font-weight: 700; letter-spacing: 1px; padding-left: 6px; background: transparent;")
        sb_layout.addWidget(cap_gen)

        self.nav = QListWidget()
        self.nav.setIconSize(QSize(16, 16))
        self.nav.setStyleSheet("""
            QListWidget {
                background: transparent;
                border: none;
                padding: 0px;
            }
            QListWidget::item {
                height: 36px;
                padding: 0 10px;
                margin-bottom: 3px;
                border-radius: 6px;
                color: #929ba8;
                font-size: 12px;
                font-weight: 500;
            }
            QListWidget::item:hover {
                background-color: #1e222b;
                color: #f0f6fc;
            }
            QListWidget::item:selected {
                background-color: #22282b;
                border: 1px solid #303a35;
                border-left: 3px solid #3fb950;
                color: #f0f6fc;
            }
        """)

        self.stack = QStackedWidget()
        self._pages: dict[str, QWidget] = {
            "Dashboard": DashboardView(core, navigate=self.navigate_to),
            "Servidores": ServerView(core),
            "Mods": ModView(core),
            "Jugadores": PlayersView(core),
            "Respaldos": BackupsView(core),
            "Métricas": MetricsView(core),
            "ZeroTier": ZeroTierView(core),
            "Rendimiento": PresetsView(core),
            "Ajustes": SettingsView(core),
            "Historial": HistoryView(core),
        }

        for name, icon_key in NAV_ITEMS:
            item = QListWidgetItem(svg_icon(icon_key, 15, "#929ba8"), f"  {name}")
            self.nav.addItem(item)
            self.stack.addWidget(self._pages[name])

        sb_layout.addWidget(self.nav, 1)

        # Tarjeta inferior de estado del entorno
        sys_box = QFrame()
        sys_box.setStyleSheet(
            "QFrame { background-color: #14171d; border: 1px solid #2a2f3a; border-radius: 7px; }"
        )
        sys_col = QVBoxLayout(sys_box)
        sys_col.setContentsMargins(10, 9, 10, 9)
        sys_col.setSpacing(6)
        sys_top = QHBoxLayout()
        sys_lbl = QLabel("● Sistema local")
        sys_lbl.setStyleSheet("color: #c9d1d9; font-size: 10px; border: none; background: transparent;")
        sys_top.addWidget(sys_lbl)
        sys_top.addStretch()
        sys_top.addWidget(Badge("Todo listo", "green"))
        sys_sub = QLabel("Java · ZeroTier · SQLite local")
        sys_sub.setStyleSheet("color: #697381; font-size: 9px; border: none; background: transparent;")
        sys_col.addLayout(sys_top)
        sys_col.addWidget(sys_sub)
        sb_layout.addWidget(sys_box)

        # --- Área derecha (Topbar + Contenido + Footer) ---
        right_shell = QWidget()
        right_layout = QVBoxLayout(right_shell)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Topbar
        topbar = QFrame()
        topbar.setFixedHeight(48)
        topbar.setStyleSheet(
            "QFrame { background-color: #0f1115; border-bottom: 1px solid #262b34; }"
        )
        tb_row = QHBoxLayout(topbar)
        tb_row.setContentsMargins(24, 0, 24, 0)
        tb_row.setSpacing(8)
        bc_ic = QLabel()
        bc_ic.setPixmap(svg_pixmap("cube", 14, "#626b77"))
        bc_ic.setStyleSheet("border: none; background: transparent;")
        bc_root = QLabel("Espacio local  /")
        bc_root.setStyleSheet("color: #8b949e; font-size: 11px; border: none; background: transparent;")
        self.bc_current = QLabel("Dashboard")
        self.bc_current.setStyleSheet("color: #f0f6fc; font-size: 11px; font-weight: 600; border: none; background: transparent;")

        conn_lbl = QLabel("●  Conexión local")
        conn_lbl.setStyleSheet("color: #8b949e; font-size: 10px; border: none; background: transparent;")
        hist_btn = QPushButton("Actividad")
        hist_btn.setProperty("variant", "ghost")
        hist_btn.setIcon(svg_icon("bell", 14, "#929ba8"))
        hist_btn.clicked.connect(lambda: self.navigate_to("Historial"))

        tb_row.addWidget(bc_ic)
        tb_row.addWidget(bc_root)
        tb_row.addWidget(self.bc_current)
        tb_row.addStretch()
        tb_row.addWidget(conn_lbl)
        tb_row.addWidget(hist_btn)

        # Footer
        footer = QFrame()
        footer.setFixedHeight(28)
        footer.setStyleSheet(
            "QFrame { background-color: #0f1115; border-top: 1px solid #252a33; }"
        )
        ft_row = QHBoxLayout(footer)
        ft_row.setContentsMargins(24, 0, 24, 0)
        self.footer_left = QLabel("● 0 servidores en ejecución · Modo local")
        self.footer_left.setStyleSheet("color: #626c79; font-size: 10px; border: none; background: transparent;")
        footer_right = QLabel("Minecraft Server Manager 1.0.0 · Hecho para tus mundos")
        footer_right.setStyleSheet("color: #626c79; font-size: 10px; border: none; background: transparent;")
        ft_row.addWidget(self.footer_left)
        ft_row.addStretch()
        ft_row.addWidget(footer_right)

        right_layout.addWidget(topbar)
        right_layout.addWidget(self.stack, 1)
        right_layout.addWidget(footer)

        container = QWidget()
        main_row = QHBoxLayout(container)
        main_row.setContentsMargins(0, 0, 0, 0)
        main_row.setSpacing(0)
        main_row.addWidget(sidebar)
        main_row.addWidget(right_shell, 1)
        self.setCentralWidget(container)

        self.nav.currentRowChanged.connect(self._on_nav_changed)
        core.events.subscribe("server.status_changed", lambda _sid, _st: self._update_footer())
        self.nav.setCurrentRow(0)
        self._update_footer()

        self.scheduler = BackupScheduler(core, self)

    def _on_nav_changed(self, row: int) -> None:
        if 0 <= row < len(NAV_ITEMS):
            name = NAV_ITEMS[row][0]
            self.bc_current.setText(name)
            self.stack.setCurrentIndex(row)
            page = self.stack.currentWidget()
            if hasattr(page, "refresh"):
                page.refresh()
            self._update_footer()

    def navigate_to(self, page_name: str) -> None:
        for idx, (name, _) in enumerate(NAV_ITEMS):
            if name == page_name:
                self.nav.setCurrentRow(idx)
                return

    def _update_footer(self) -> None:
        servers = self._core.servers.list_servers()
        running = sum(1 for s in servers if self._core.controller.is_running(s.id))
        plural = "es" if running != 1 else ""
        self.footer_left.setText(f"● {running} servidor{plural} en ejecución  ·  {len(servers)} registrado(s)  ·  Modo local")

    def closeEvent(self, event) -> None:
        self._core.close()
        super().closeEvent(event)