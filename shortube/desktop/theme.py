from __future__ import annotations

import json

from shortube.config import get_settings
from shortube.template_loader import load_template

DEFAULT_ACCENT = "#4caf50"

_CARD_BG = "#1a1e26"
_SIDEBAR_BG = "#12151b"
_BG = "#0f1115"
_TEXT = "#e6e9ef"
_MUTED = "#8b93a3"
_BORDER = "#2a2f3a"


def accent_color() -> str:
    try:
        data = load_template(get_settings().template)
        return str(data.get("accent", DEFAULT_ACCENT))
    except (OSError, json.JSONDecodeError):
        return DEFAULT_ACCENT


def build_stylesheet(accent: str = "") -> str:
    accent = accent or accent_color()
    return f"""
    * {{
        font-family: 'Segoe UI', 'Segoe UI Variable', Arial, sans-serif;
        font-size: 13px;
        color: {_TEXT};
    }}
    QMainWindow, QDialog, QWizard, QStackedWidget {{
        background-color: {_BG};
    }}
    QWidget#sidebar {{
        background-color: {_SIDEBAR_BG};
        border-right: 1px solid {_BORDER};
    }}
    QWidget#header {{
        background-color: {_SIDEBAR_BG};
        border-bottom: 1px solid {_BORDER};
    }}
    QLabel#appTitle {{
        font-size: 18px;
        font-weight: 700;
        color: {accent};
    }}
    QLabel#appSubtitle {{
        font-size: 12px;
        color: {_MUTED};
    }}
    QPushButton#navButton {{
        background: transparent;
        border: none;
        text-align: left;
        padding: 10px 16px;
        border-radius: 8px;
        color: {_MUTED};
        font-size: 14px;
    }}
    QPushButton#navButton:hover {{
        background-color: #1f2530;
        color: {_TEXT};
    }}
    QPushButton#navButton:checked {{
        background-color: {accent};
        color: #ffffff;
        font-weight: 600;
    }}
    QPushButton {{
        background-color: #232a36;
        border: 1px solid {_BORDER};
        border-radius: 8px;
        padding: 8px 16px;
    }}
    QPushButton:hover {{ background-color: #2b3341; }}
    QPushButton:pressed {{ background-color: #1d232d; }}
    QPushButton:disabled {{ color: {_MUTED}; background-color: #1a1f28; }}
    QPushButton#primary {{
        background-color: {accent};
        border: none;
        color: #ffffff;
        font-weight: 600;
    }}
    QPushButton#primary:hover {{ background-color: {accent}; }}
    QPushButton#danger {{
        background-color: #b3261e;
        border: none;
        color: #ffffff;
    }}
    QPushButton#danger:hover {{ background-color: #c9372e; }}
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit, QPlainTextEdit {{
        background-color: #141821;
        border: 1px solid {_BORDER};
        border-radius: 8px;
        padding: 7px 10px;
        selection-background-color: {accent};
    }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus,
    QTextEdit:focus, QPlainTextEdit:focus {{
        border: 1px solid {accent};
    }}
    QComboBox::drop-down {{ border: none; width: 22px; }}
    QComboBox::down-arrow {{
        image: none;
        border-left: 5px solid transparent;
        border-right: 5px solid transparent;
        border-top: 6px solid {_MUTED};
        margin-right: 8px;
    }}
    QComboBox QAbstractItemView {{
        background-color: #1a1e26;
        border: 1px solid {_BORDER};
        selection-background-color: {accent};
    }}
    QProgressBar {{
        background-color: #141821;
        border: 1px solid {_BORDER};
        border-radius: 8px;
        text-align: center;
        color: {_TEXT};
        height: 18px;
    }}
    QProgressBar::chunk {{
        background-color: {accent};
        border-radius: 7px;
    }}
    QTableWidget, QTableView {{
        background-color: #141821;
        border: 1px solid {_BORDER};
        border-radius: 8px;
        gridline-color: {_BORDER};
        selection-background-color: {accent};
        selection-color: #ffffff;
    }}
    QHeaderView::section {{
        background-color: #1a1e26;
        border: none;
        border-bottom: 1px solid {_BORDER};
        padding: 8px;
        font-weight: 600;
        color: {_MUTED};
    }}
    QTableWidget::item {{ padding: 6px; }}
    QTabWidget::pane {{
        border: 1px solid {_BORDER};
        border-radius: 8px;
        background-color: #141821;
    }}
    QTabBar::tab {{
        background: transparent;
        padding: 8px 18px;
        color: {_MUTED};
        border-bottom: 2px solid transparent;
    }}
    QTabBar::tab:selected {{ color: {_TEXT}; border-bottom: 2px solid {accent}; }}
    QTabBar::tab:hover {{ color: {_TEXT}; }}
    QGroupBox {{
        border: 1px solid {_BORDER};
        border-radius: 8px;
        margin-top: 12px;
        padding-top: 10px;
        font-weight: 600;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 6px;
        color: {_MUTED};
    }}
    QCheckBox, QRadioButton {{ spacing: 8px; }}
    QCheckBox::indicator, QRadioButton::indicator {{
        width: 16px;
        height: 16px;
        border: 1px solid {_BORDER};
        border-radius: 4px;
        background-color: #141821;
    }}
    QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
        background-color: {accent};
        border-color: {accent};
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: #2b3341;
        border-radius: 5px;
        min-height: 30px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QStatusBar {{ background: {_SIDEBAR_BG}; color: {_MUTED}; }}
    QMessageBox, QDialog {{
        background-color: {_BG};
    }}
    QToolTip {{
        background-color: #232a36;
        color: {_TEXT};
        border: 1px solid {_BORDER};
        padding: 4px 8px;
    }}
    """
