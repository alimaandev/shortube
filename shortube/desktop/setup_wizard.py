from __future__ import annotations

from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)

from shortube.config import get_settings
from shortube.desktop.workers import run_in_thread
from shortube.settings_env import save_settings
from shortube.template_loader import DEFAULTS

PROVIDER_DEFAULT_MODELS = {
    "groq": "llama-3.3-70b-versatile",
    "openrouter": "meta-llama/llama-4-scout:free",
    "ollama": "qwen2.5:7b",
}


def needs_setup() -> bool:
    from pathlib import Path

    cfg = get_settings()
    if not Path(cfg.base_dir / ".env").exists():
        return True
    if cfg.llm_provider == "ollama":
        return not cfg.ollama_base_url
    if cfg.llm_provider == "groq":
        return not cfg.groq_api_key
    return not cfg.openrouter_api_key


class _LlmPage(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Language Model")
        self.setSubTitle(
            "Shortube uses an LLM to write scripts. Groq and OpenRouter need an "
            "API key; Ollama runs locally for free."
        )

        form = QFormLayout(self)
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["groq", "openrouter", "ollama"])
        self.provider_combo.setCurrentText(get_settings().llm_provider)
        form.addRow("Provider", self.provider_combo)

        self.model_input = QLineEdit()
        form.addRow("Model", self.model_input)

        self.key_input = QLineEdit()
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("API key", self.key_input)

        self.url_input = QLineEdit("http://localhost:11434")
        form.addRow("Ollama base URL", self.url_input)

        self.test_btn = QPushButton("Test Connection")
        self.test_btn.clicked.connect(self._test)
        self.status = QLabel("")
        form.addRow("", self.test_btn)
        form.addRow("", self.status)

        self.provider_combo.currentTextChanged.connect(self._sync_fields)
        self._sync_fields(self.provider_combo.currentText())

    def _sync_fields(self, provider: str) -> None:
        self.model_input.setText(PROVIDER_DEFAULT_MODELS.get(provider, ""))
        is_ollama = provider == "ollama"
        self.key_input.setEnabled(not is_ollama)
        self.url_input.setEnabled(is_ollama)
        self.key_input.setPlaceholderText(
            "API key" if not is_ollama else ""
        )
        self.url_input.setPlaceholderText("http://localhost:11434" if is_ollama else "")

    def _test(self) -> None:
        from shortube.llm import create_llm

        provider = self.provider_combo.currentText()
        api_key = "" if provider == "ollama" else self.key_input.text().strip()
        model = self.model_input.text().strip()
        self.test_btn.setEnabled(False)
        self.status.setText("Testing...")

        def work() -> str:
            llm = create_llm(provider=provider, api_key=api_key, model=model)
            return llm.generate(
                "You are a helper.", "Reply with exactly: OK", max_tokens=8
            )

        def done(reply: str) -> None:
            self.test_btn.setEnabled(True)
            ok = "ok" in reply.lower()
            self.status.setText("Connected" if ok else f"Unexpected reply: {reply[:40]}")
            self.status.setStyleSheet("color: #4caf50;" if ok else "color: #ef5350;")

        def failed(error: str) -> None:
            self.test_btn.setEnabled(True)
            self.status.setText(f"Failed: {error[:90]}")
            self.status.setStyleSheet("color: #ef5350;")

        run_in_thread(work, done, failed)

    def values(self) -> dict:
        return {
            "llm_provider": self.provider_combo.currentText(),
            "llm_model": self.model_input.text().strip(),
        }


class _LookPage(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Look and Feel")
        self.setSubTitle("Choose the visual template and output quality.")

        form = QFormLayout(self)
        self.template_combo = QComboBox()
        self.template_combo.addItem(
            f'{DEFAULTS.get("name", "premium")} ({DEFAULTS.get("id", "premium")})',
            DEFAULTS.get("id", "premium"),
        )
        form.addRow("Template", self.template_combo)
        self.quality_combo = QComboBox()
        self.quality_combo.addItem("Fast (draft, quick renders)", "fast")
        self.quality_combo.addItem("Standard (balanced)", "standard")
        self.quality_combo.addItem("Pro (best quality)", "pro")
        self.quality_combo.setCurrentIndex(1)
        form.addRow("Quality preset", self.quality_combo)

    def values(self) -> dict:
        return {
            "template": self.template_combo.currentData(),
            "quality": self.quality_combo.currentData(),
        }


class SetupWizard(QWizard):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Welcome to Shortube Studio")
        self.setMinimumSize(560, 420)
        self.llm_page = _LlmPage()
        self.look_page = _LookPage()
        self.addPage(self.llm_page)
        self.addPage(self.look_page)
        self.button(QWizard.WizardButton.FinishButton).clicked.connect(self._finish)

    def _finish(self) -> None:
        payload = self.llm_page.values()
        payload.update(self.look_page.values())
        llm_key = self.llm_page.key_input.text().strip()
        provider = self.llm_page.provider_combo.currentText()
        if provider == "groq" and llm_key:
            payload["groq_api_key"] = llm_key
        if provider == "openrouter" and llm_key:
            payload["openrouter_api_key"] = llm_key
        if provider == "ollama":
            payload["ollama_base_url"] = self.llm_page.url_input.text().strip()
        try:
            save_settings(payload)
        except Exception:
            pass
