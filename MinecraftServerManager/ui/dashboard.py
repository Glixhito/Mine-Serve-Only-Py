"""Dashboard principal: métricas resumen, tarjetas de servidores y actividad reciente."""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton,
                               QScrollArea, QVBoxLayout, QWidget)

from ui.widgets.components import Badge, PageHeader, Panel, style_button
from ui.widgets.icons import svg_pixmap


class DashboardView(QWidget):
    def __init__(self, core, navigate=None) -> None:
        super().__init__()
        self._core = core
        self._navigate = navigate or (lambda _page: None)

        status_chip = Badge("Todo bajo control", "green", dot=True)
        header = PageHeader(
            "Tu próximo mundo empieza aquí.",
            "Todo lo que necesitas para mantener tus mundos en marcha.",
            action_widget=status_chip,
        )

        # --- KPIs superiores ---
        kpi_grid = QGridLayout()
        kpi_grid.setSpacing(14)

        self.kpi_total = QLabel("0")
        self.kpi_total_sub = QLabel("Vanilla, Fabric, Forge y NeoForge")
        card1 = self._stat_card("Servidores registrados", "server", self.kpi_total, self.kpi_total_sub)

        self.kpi_active = QLabel("0")
        self.kpi_active_sub = QLabel("En ejecución ahora mismo")
        card2 = self._stat_card("Servidores activos", "activity", self.kpi_active, self.kpi_active_sub, accent=True)

        self.kpi_ram = QLabel("0 MB")
        self.kpi_ram_sub = QLabel("Memoria máxima asignada a servidores activos")
        card3 = self._stat_card("RAM asignada activa", "memory", self.kpi_ram, self.kpi_ram_sub)

        kpi_grid.addWidget(card1, 0, 0)
        kpi_grid.addWidget(card2, 0, 1)
        kpi_grid.addWidget(card3, 0, 2)

        # --- Encabezado de sección Servidores ---
        sec_row = QHBoxLayout()
        sec_title = QLabel("Tus servidores")
        sec_title.setStyleSheet("font-size: 16px; font-weight: 600; color: #f0f6fc;")
        go_servers = QPushButton("Ir a Servidores")
        style_button(go_servers, "primary", "plus")
        go_servers.clicked.connect(lambda: self._navigate("Servidores"))
        sec_row.addWidget(sec_title)
        sec_row.addStretch()
        sec_row.addWidget(go_servers)

        self.servers_grid = QGridLayout()
        self.servers_grid.setSpacing(13)

        # --- Panel inferior: Actividad reciente ---
        view_all = QPushButton("Ver historial completo")
        style_button(view_all, "ghost", "arrow")
        view_all.clicked.connect(lambda: self._navigate("Historial"))
        self.activity_panel = Panel("Actividad reciente", "clock", aside=view_all)

        # Scroll principal
        scroll_body = QWidget()
        body_col = QVBoxLayout(scroll_body)
        body_col.setContentsMargins(24, 20, 24, 20)
        body_col.setSpacing(18)
        body_col.addWidget(header)
        body_col.addLayout(kpi_grid)
        body_col.addLayout(sec_row)
        body_col.addLayout(self.servers_grid)
        body_col.addWidget(self.activity_panel)
        body_col.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(scroll_body)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

        core.events.subscribe("server.status_changed", lambda _sid, _st: self.refresh())
        self.refresh()

    def _stat_card(self, title: str, icon_name: str, value_lbl: QLabel,
                   sub_lbl: QLabel, accent: bool = False) -> QFrame:
        card = QFrame()
        card.setObjectName("Panel")
        col = QVBoxLayout(card)
        col.setContentsMargins(16, 14, 16, 14)
        col.setSpacing(6)

        top = QHBoxLayout()
        t = QLabel(title)
        t.setStyleSheet("color: #a0a8b4; font-size: 11px; font-weight: 500; background: transparent;")
        ic = QLabel()
        ic.setPixmap(svg_pixmap(icon_name, 15, "#626c7a"))
        ic.setStyleSheet("background: transparent;")
        top.addWidget(t)
        top.addStretch()
        top.addWidget(ic)

        color = "#3fb950" if accent else "#f0f6fc"
        value_lbl.setStyleSheet(
            f"font-size: 26px; font-weight: 700; color: {color}; "
            "font-family: 'JetBrains Mono', 'Inter', sans-serif; background: transparent;"
        )
        sub_lbl.setStyleSheet("color: #78828f; font-size: 11px; background: transparent;")

        col.addLayout(top)
        col.addWidget(value_lbl)
        col.addWidget(sub_lbl)
        return card

    def refresh(self) -> None:
        servers = self._core.servers.list_servers()
        running_servers = [s for s in servers if self._core.controller.is_running(s.id)]
        total_ram = sum(s.max_ram for s in running_servers)

        self.kpi_total.setText(str(len(servers)))
        self.kpi_active.setText(str(len(running_servers)))
        self.kpi_ram.setText(f"{total_ram:,} MB")

        # Limpiar tarjetas previas
        while self.servers_grid.count():
            item = self.servers_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not servers:
            empty = Panel()
            lbl = QLabel("Aún no tienes servidores registrados. Pulsa «Ir a Servidores» para crear tu primer mundo.")
            lbl.setStyleSheet("color: #8b949e; font-size: 12px;")
            empty.body_layout.addWidget(lbl)
            self.servers_grid.addWidget(empty, 0, 0)
        else:
            for idx, record in enumerate(servers):
                running = self._core.controller.is_running(record.id)
                card = self._build_server_card(record, running)
                self.servers_grid.addWidget(card, idx // 2, idx % 2)

        # Actividad reciente
        while self.activity_panel.body_layout.count():
            item = self.activity_panel.body_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        recent = self._core.operations.recent(None)[:4]
        if not recent:
            empty_act = QLabel("Sin operaciones recientes registradas.")
            empty_act.setStyleSheet("color: #78828f; font-size: 11px;")
            self.activity_panel.body_layout.addWidget(empty_act)
        else:
            for row in recent:
                line = QWidget()
                r = QHBoxLayout(line)
                r.setContentsMargins(0, 4, 0, 4)
                op = QLabel(f"{row['operation_type']}  ·  {row['server_name'] or '(eliminado)'}")
                op.setStyleSheet("color: #e1e6ed; font-size: 12px; font-weight: 500;")
                st = Badge(row["status"], "green" if row["status"] == "ok" else "amber")
                when = datetime.fromisoformat(row["created_at"]).astimezone().strftime("%H:%M:%S")
                tm = QLabel(when)
                tm.setStyleSheet("color: #626d7a; font-size: 11px; font-family: 'JetBrains Mono', monospace;")
                r.addWidget(op)
                r.addWidget(st)
                r.addStretch()
                r.addWidget(tm)
                self.activity_panel.body_layout.addWidget(line)

    def _build_server_card(self, record, running: bool) -> QFrame:
        card = QFrame()
        card.setObjectName("PanelHero" if running else "Panel")
        col = QVBoxLayout(card)
        col.setContentsMargins(15, 14, 15, 14)
        col.setSpacing(10)

        top = QHBoxLayout()
        art = QLabel()
        art.setPixmap(svg_pixmap("cube", 20, "#3fb950" if running else "#8b949e"))
        art.setStyleSheet("background: #1e222b; border: 1px solid #303640; border-radius: 7px; padding: 7px;")

        info_col = QVBoxLayout()
        info_col.setSpacing(2)
        name_lbl = QLabel(record.name)
        name_lbl.setStyleSheet("font-size: 13px; font-weight: 600; color: #f0f6fc; background: transparent;")
        meta_lbl = QLabel(f"Minecraft {record.minecraft_version}  ·  {record.server_type}  ·  {record.max_ram} MB")
        meta_lbl.setStyleSheet("font-size: 11px; color: #8b949e; background: transparent;")
        info_col.addWidget(name_lbl)
        info_col.addWidget(meta_lbl)

        badge = Badge("En ejecución" if running else "Detenido", "green" if running else "neutral", dot=True)
        top.addWidget(art)
        top.addLayout(info_col, 1)
        top.addWidget(badge)

        bot = QHBoxLayout()
        open_btn = QPushButton("Abrir consola")
        style_button(open_btn, "default", "terminal")
        open_btn.clicked.connect(lambda: self._navigate("Servidores"))
        bot.addWidget(open_btn)
        bot.addStretch()

        col.addLayout(top)
        col.addLayout(bot)
        return card