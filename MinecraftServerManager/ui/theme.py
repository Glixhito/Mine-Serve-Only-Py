"""Sistema de diseño visual (colores, tipografía y hoja de estilos global QSS)."""
from __future__ import annotations

PALETTE = {
    "bg_canvas": "#0f1115",
    "bg_surface": "#161920",
    "bg_elevated": "#1e222b",
    "bg_subtle": "#14171d",
    "bg_console": "#0b0d10",
    "border": "#2a2f3a",
    "border_subtle": "#262b34",
    "border_strong": "#39414d",
    "text_primary": "#f0f6fc",
    "text_secondary": "#c9d1d9",
    "text_muted": "#8b949e",
    "text_dim": "#626d7a",
    "green": "#3fb950",
    "green_btn": "#2ea043",
    "green_border": "#3cad51",
    "green_bg": "#151b17",
    "blue": "#58a6ff",
    "amber": "#d29922",
    "red": "#f85149",
}

GLOBAL_QSS = """
/* --- Base: no se pone fondo a todos los QWidget; así las etiquetas y contenedores no tapan los paneles --- */
QWidget {
    color: #f0f6fc;
    font-family: "Inter", "Segoe UI", sans-serif;
    font-size: 13px;
}

QMainWindow, QStackedWidget {
    background-color: #0f1115;
}

QLabel {
    background: transparent;
}

/* --- Scrollbars minimalistas --- */
QScrollArea {
    border: none;
    background-color: #0f1115;
}
QWidget#qt_scrollarea_viewport {
    background-color: #0f1115;
}
QScrollArea > QWidget > QWidget {
    background: transparent;
}
QScrollBar:vertical {
    background: transparent;
    width: 6px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #303642;
    border-radius: 3px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover {
    background: #484f58;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    height: 0px;
    background: none;
}
QScrollBar:horizontal {
    background: transparent;
    height: 6px;
    margin: 2px;
}
QScrollBar::handle:horizontal {
    background: #303642;
    border-radius: 3px;
    min-width: 24px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* --- Inputs, SpinBoxes y Selects --- */
QLineEdit, QComboBox, QSpinBox {
    background-color: #1e222b;
    border: 1px solid #2a2f3a;
    border-radius: 6px;
    color: #e1e6ed;
    min-height: 33px;
    padding: 0 10px;
    font-size: 12px;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border: 1px solid #3fb950;
}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {
    background-color: #14171d;
    color: #596371;
    border-color: #222630;
}
QSpinBox {
    font-family: "JetBrains Mono", "Consolas", monospace;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox QAbstractItemView {
    background-color: #161920;
    border: 1px solid #39414d;
    selection-background-color: #202923;
    selection-color: #f0f6fc;
    outline: none;
}

/* --- Botones --- */
QPushButton {
    background-color: #1e222b;
    border: 1px solid #303540;
    color: #d3dae3;
    font-weight: 500;
    font-size: 12px;
    border-radius: 6px;
    min-height: 32px;
    padding: 0 12px;
}
QPushButton:hover:enabled {
    background-color: #292e38;
    border-color: #434b58;
    color: #f0f6fc;
}
QPushButton:disabled {
    background-color: #161920;
    border-color: #232832;
    color: #555e6b;
}

QPushButton[variant="primary"] {
    background-color: #2ea043;
    border: 1px solid #3cad51;
    color: #f0f6fc;
    font-weight: 600;
}
QPushButton[variant="primary"]:hover:enabled {
    background-color: #3fb950;
    border-color: #54c964;
}
QPushButton[variant="primary"]:disabled {
    background-color: #1b3824;
    border-color: #23472e;
    color: #5d7a64;
}

QPushButton[variant="danger-subtle"] {
    background-color: rgba(248, 81, 73, 0.08);
    border: 1px solid rgba(248, 81, 73, 0.25);
    color: #f07873;
}
QPushButton[variant="danger-subtle"]:hover:enabled {
    background-color: rgba(248, 81, 73, 0.18);
    border-color: rgba(248, 81, 73, 0.45);
}

QPushButton[variant="accent-outline"] {
    background-color: rgba(46, 160, 67, 0.07);
    border: 1px solid rgba(46, 160, 67, 0.35);
    color: #69c278;
}
QPushButton[variant="accent-outline"]:hover:enabled {
    background-color: rgba(46, 160, 67, 0.15);
    border-color: #3fb950;
}

QPushButton[variant="ghost"] {
    background-color: transparent;
    border: 1px solid transparent;
    color: #8b949e;
}
QPushButton[variant="ghost"]:hover:enabled {
    background-color: #1e222b;
    color: #f0f6fc;
}

/* --- Checkboxes --- */
QCheckBox {
    spacing: 8px;
    color: #cbd3dd;
    font-size: 12px;
    background: transparent;
}
QCheckBox::indicator {
    width: 15px;
    height: 15px;
    border-radius: 4px;
    border: 1px solid #39414d;
    background-color: #1e222b;
}
QCheckBox::indicator:checked {
    background-color: #2ea043;
    border-color: #3fb950;
}

/* --- Paneles --- */
QFrame#Panel {
    background-color: #161920;
    border: 1px solid #2a2f3a;
    border-radius: 8px;
}
QFrame#PanelHeader {
    background-color: transparent;
    border-bottom: 1px solid #282d37;
}
QFrame#PanelHero {
    background-color: #161d1a;
    border: 1px solid #30473a;
    border-radius: 8px;
}
QFrame#AddressBox {
    background-color: #101712;
    border: 1px solid #34483a;
    border-radius: 6px;
}

/* --- Tablas --- */
QTableWidget {
    background-color: #161920;
    border: none;
    gridline-color: #272d37;
    selection-background-color: #202a25;
    selection-color: #f0f6fc;
    outline: none;
    font-size: 12px;
}
QTableWidget::item {
    padding: 8px 10px;
    border-bottom: 1px solid #272d37;
}
QTableWidget::item:selected {
    background-color: #202a25;
    color: #f0f6fc;
}
QHeaderView::section {
    background-color: #1b1f27;
    color: #8b96a5;
    font-size: 11px;
    font-weight: 600;
    padding: 9px 10px;
    border: none;
    border-bottom: 1px solid #2a2f3a;
}

/* --- Listas --- */
QListWidget {
    background-color: #161920;
    border: 1px solid #2a2f3a;
    border-radius: 7px;
    padding: 4px;
    outline: none;
}
QListWidget::item {
    padding: 8px 10px;
    border-radius: 5px;
    color: #c9d1d9;
}
QListWidget::item:hover {
    background-color: #1e222b;
}
QListWidget::item:selected {
    background-color: #1e2922;
    border-left: 2px solid #3fb950;
    color: #f0f6fc;
}

/* --- Pestañas internas --- */
QTabWidget::pane {
    border: 1px solid #2a2f3a;
    background-color: #161920;
    border-radius: 6px;
    top: -1px;
}
QTabBar::tab {
    background-color: #101318;
    color: #8b96a5;
    border: 1px solid #282f39;
    padding: 6px 14px;
    margin-right: 4px;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
    font-size: 11px;
    font-weight: 500;
}
QTabBar::tab:selected {
    background-color: #252b35;
    color: #e3e9ef;
    border-color: #343c48;
}

/* --- Diálogos, mensajes y tooltips --- */
QDialog, QMessageBox {
    background-color: #161920;
}
QToolTip {
    background-color: #1e222b;
    color: #f0f6fc;
    border: 1px solid #39414d;
    padding: 4px 8px;
}
"""