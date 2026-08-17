from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from shortube.config import get_settings
from shortube.desktop.workers import run_in_thread
from shortube.quality import QUALITY_PRESETS
from shortube.settings_env import read_env, save_settings
from shortube.template_loader import DEFAULTS

PROVIDER_DEFAULT_MODELS = {
    "groq": "llama-3.3-70b-versatile",
    "openrouter": "meta-llama/llama-4-scout:free",
    "ollama": "qwen2.5:7b",
}


def _label_row(layout: QFormLayout, label: str, widget: QWidget, hint: str = "") -> None:
    layout.addRow(label, widget)
    if hint:
        hint_label = QLabel(hint)
        hint_label.setStyleSheet("color: #8b93a3; font-size: 11px;")
        layout.addRow("", hint_label)


class SettingsPage(QWidget):
    def __init__(self, window) -> None:
        super().__init__()
        self.window = window

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_llm_tab(), "LLM")
        self.tabs.addTab(self._build_voice_tab(), "Voice")
        self.tabs.addTab(self._build_video_tab(), "Video & Quality")
        self.tabs.addTab(self._build_upload_tab(), "Upload")
        self.tabs.addTab(self._build_advanced_tab(), "Advanced")
        root.addWidget(self.tabs, 1)

        save_row = QHBoxLayout()
        save_row.addStretch(1)
        self.save_btn = QPushButton("Save Settings")
        self.save_btn.setObjectName("primary")
        self.save_btn.clicked.connect(self._save)
        save_row.addWidget(self.save_btn)
        root.addLayout(save_row)

    def _widget_group(self, title: str) -> tuple[QGroupBox, QFormLayout]:
        box = QGroupBox(title)
        layout = QFormLayout(box)
        return box, layout

    def _build_llm_tab(self) -> QWidget:
        cfg = get_settings()
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(16, 16, 16, 16)

        group, form = self._widget_group("Language Model")
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["groq", "openrouter", "ollama"])
        self.provider_combo.setCurrentText(cfg.llm_provider)
        form.addRow("Provider", self.provider_combo)
        self.model_input = QLineEdit(cfg.llm_model)
        form.addRow("Model", self.model_input)
        self.discovery_input = QLineEdit(
            cfg.discovery_model or cfg.llm_model
        )
        _label_row(
            form, "Discovery model",
            self.discovery_input,
            "Used for trend refinement; blank = same as model",
        )
        self.temp_slider = QSlider()
        self.temp_slider.setOrientation(Qt.Orientation.Horizontal)
        self.temp_slider.setRange(0, 150)
        self.temp_slider.setValue(int(cfg.llm_temperature * 100))
        self.temp_label = QLabel(f"{cfg.llm_temperature:.2f}")
        row = QHBoxLayout()
        row.addWidget(self.temp_slider, 1)
        row.addWidget(self.temp_label)
        temp_widget = QWidget()
        temp_widget.setLayout(row)
        form.addRow("Temperature", temp_widget)

        self.groq_key = QLineEdit()
        self.groq_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.groq_key.setPlaceholderText(
            "Set" if cfg.groq_api_key else "groq API key (gsk_...)"
        )
        form.addRow("Groq API key", self.groq_key)
        self.openrouter_key = QLineEdit()
        self.openrouter_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.openrouter_key.setPlaceholderText(
            "Set" if cfg.openrouter_api_key else "OpenRouter API key (sk-or-...)"
        )
        form.addRow("OpenRouter key", self.openrouter_key)
        self.ollama_url = QLineEdit(cfg.ollama_base_url)
        form.addRow("Ollama base URL", self.ollama_url)
        self.test_btn = QPushButton("Test Connection")
        self.test_btn.clicked.connect(self._test_llm)
        self.test_status = QLabel("")
        test_row = QHBoxLayout()
        test_row.addWidget(self.test_btn)
        test_row.addWidget(self.test_status, 1)
        form.addRow("", test_row)
        outer.addWidget(group)
        outer.addStretch(1)

        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        self.temp_slider.valueChanged.connect(
            lambda v: self.temp_label.setText(f"{v / 100:.2f}")
        )
        return page

    def _on_provider_changed(self, provider: str) -> None:
        self.model_input.setText(PROVIDER_DEFAULT_MODELS.get(provider, ""))

    def _build_voice_tab(self) -> QWidget:
        cfg = get_settings()
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(16, 16, 16, 16)

        group, form = self._widget_group("Voiceover")
        self.voice_name = QLineEdit(cfg.voice_name)
        form.addRow("Voice (edge-tts)", self.voice_name)
        self.voice_speed = QDoubleSpinBox()
        self.voice_speed.setRange(0.5, 2.0)
        self.voice_speed.setSingleStep(0.05)
        self.voice_speed.setValue(cfg.voice_speed)
        form.addRow("Speed", self.voice_speed)
        self.voice_volume = QDoubleSpinBox()
        self.voice_volume.setRange(0.0, 2.0)
        self.voice_volume.setSingleStep(0.1)
        self.voice_volume.setValue(cfg.voice_volume)
        form.addRow("Volume", self.voice_volume)
        outer.addWidget(group)
        outer.addStretch(1)
        return page

    def _build_video_tab(self) -> QWidget:
        cfg = get_settings()
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(16, 16, 16, 16)

        group, form = self._widget_group("Quality")
        self.quality_combo = QComboBox()
        for key, preset in QUALITY_PRESETS.items():
            self.quality_combo.addItem(f"{key} — {preset.label}", key)
        idx = self.quality_combo.findData(cfg.quality)
        if idx >= 0:
            self.quality_combo.setCurrentIndex(idx)
        form.addRow("Preset", self.quality_combo)
        outer.addWidget(group)

        group2, form2 = self._widget_group("Canvas")
        self.width_spin = QSpinBox()
        self.width_spin.setRange(240, 4320)
        self.width_spin.setValue(cfg.video_width)
        form2.addRow("Width (px)", self.width_spin)
        self.height_spin = QSpinBox()
        self.height_spin.setRange(240, 4320)
        self.height_spin.setValue(cfg.video_height)
        form2.addRow("Height (px)", self.height_spin)
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(10, 60)
        self.fps_spin.setValue(cfg.video_fps)
        form2.addRow("FPS (baseline)", self.fps_spin)
        self.bumper_spin = QDoubleSpinBox()
        self.bumper_spin.setRange(0.5, 5.0)
        self.bumper_spin.setSingleStep(0.1)
        self.bumper_spin.setValue(cfg.bumper_duration)
        form2.addRow("Bumper duration (s)", self.bumper_spin)
        self.transition_spin = QDoubleSpinBox()
        self.transition_spin.setRange(0.1, 1.0)
        self.transition_spin.setSingleStep(0.05)
        self.transition_spin.setValue(cfg.transition_duration)
        form2.addRow("Transition duration (s)", self.transition_spin)
        outer.addWidget(group2)

        group3, form3 = self._widget_group("Template")
        self.template_combo = QComboBox()
        self._load_templates()
        current = cfg.template or DEFAULTS.get("id", "premium")
        idx = self.template_combo.findData(current)
        if idx >= 0:
            self.template_combo.setCurrentIndex(idx)
        form3.addRow("Visual template", self.template_combo)
        outer.addWidget(group3)
        outer.addStretch(1)
        return page

    def _load_templates(self) -> None:
        import json

        self.template_combo.clear()
        cfg = get_settings()
        templates_dir = cfg.base_dir / "templates"
        seen: set[str] = set()
        if templates_dir.exists():
            for f in sorted(templates_dir.glob("*.json")):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    tid = str(data.get("id", f.stem))
                    name = str(data.get("name", f.stem))
                except (json.JSONDecodeError, OSError):
                    continue
                self.template_combo.addItem(f"{name} ({tid})", tid)
                seen.add(tid)
        default_id = str(DEFAULTS.get("id", "premium"))
        if default_id not in seen:
            self.template_combo.addItem(
                f'{DEFAULTS.get("name", default_id)} ({default_id})', default_id
            )

    def _build_upload_tab(self) -> QWidget:
        cfg = get_settings()
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(16, 16, 16, 16)

        group, form = self._widget_group("YouTube")
        self.privacy_combo = QComboBox()
        self.privacy_combo.addItems(["private", "unlisted", "public"])
        self.privacy_combo.setCurrentText(cfg.upload_privacy)
        form.addRow("Privacy", self.privacy_combo)
        self.category_input = QLineEdit(cfg.upload_category)
        form.addRow("Category ID", self.category_input)
        self.language_input = QLineEdit(cfg.upload_language)
        form.addRow("Language", self.language_input)
        self.publish_at_input = QLineEdit(cfg.upload_publish_at)
        _label_row(
            form, "Publish at",
            self.publish_at_input,
            "ISO 8601, e.g. 2026-08-20T15:00:00Z (empty = now)",
        )
        self.channel_combo = QComboBox()
        self.channel_combo.setEditable(True)
        self.channel_combo.setPlaceholderText("Select a channel...")
        if cfg.upload_channel_id:
            self.channel_combo.setCurrentText(cfg.upload_channel_id)
        form.addRow("Channel", self.channel_combo)
        self.channels_btn = QPushButton("Load Channels / Connect YouTube")
        self.channels_btn.clicked.connect(self._load_channels)
        self.channels_status = QLabel("")
        row = QHBoxLayout()
        row.addWidget(self.channels_btn)
        row.addWidget(self.channels_status, 1)
        form.addRow("", row)
        outer.addWidget(group)
        outer.addStretch(1)
        return page

    def _build_advanced_tab(self) -> QWidget:
        cfg = get_settings()
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(16, 16, 16, 16)

        group, form = self._widget_group("Media")
        self.image_provider_combo = QComboBox()
        self.image_provider_combo.addItems(["auto", "pexels", "pixabay", "pollinations"])
        self.image_provider_combo.setCurrentText(cfg.image_provider)
        form.addRow("Image provider", self.image_provider_combo)
        self.prefer_videos = QCheckBox()
        self.prefer_videos.setChecked(cfg.media_prefer_videos)
        form.addRow("Prefer videos", self.prefer_videos)
        outer.addWidget(group)

        group2, form2 = self._widget_group("Audio")
        self.music_path = QLineEdit(cfg.background_music_path)
        form2.addRow("Music path", self.music_path)
        self.music_volume = QDoubleSpinBox()
        self.music_volume.setRange(0.0, 100.0)
        self.music_volume.setValue(cfg.music_volume)
        form2.addRow("Music volume", self.music_volume)
        self.duck_threshold = QDoubleSpinBox()
        self.duck_threshold.setRange(0.0, 30.0)
        self.duck_threshold.setValue(cfg.duck_threshold)
        form2.addRow("Duck threshold", self.duck_threshold)
        self.sfx_enabled = QCheckBox()
        self.sfx_enabled.setChecked(cfg.sfx_enabled)
        form2.addRow("Sound effects", self.sfx_enabled)
        self.sfx_dir = QLineEdit(cfg.sfx_dir)
        form2.addRow("SFX folder", self.sfx_dir)
        outer.addWidget(group2)

        group3, form3 = self._widget_group("Render")
        self.concurrency_spin = QSpinBox()
        self.concurrency_spin.setRange(0, 32)
        self.concurrency_spin.setSpecialValueText("auto")
        self.concurrency_spin.setValue(cfg.remotion_concurrency)
        _label_row(
            form3, "Remotion concurrency",
            self.concurrency_spin,
            "0 = use the quality preset default",
        )
        self.caption_font_size = QSpinBox()
        self.caption_font_size.setRange(20, 96)
        self.caption_font_size.setValue(cfg.caption_font_size)
        form3.addRow("Caption font size", self.caption_font_size)
        outer.addWidget(group3)
        outer.addStretch(1)
        return page

    def _test_llm(self) -> None:
        from shortube.llm import create_llm

        provider = self.provider_combo.currentText()
        model = self.model_input.text().strip()
        api_key = {
            "groq": self.groq_key.text().strip()
            or (get_settings().groq_api_key if provider == "groq" else ""),
            "openrouter": self.openrouter_key.text().strip()
            or (get_settings().openrouter_api_key if provider == "openrouter" else ""),
            "ollama": "dummy",
        }[provider]

        self.test_btn.setEnabled(False)
        self.test_status.setText("Testing...")

        def work() -> str:
            llm = create_llm(provider=provider, api_key=api_key, model=model)
            return llm.generate(
                "You are a helper.", "Reply with exactly: OK", max_tokens=8
            )

        def done(reply: str) -> None:
            self.test_btn.setEnabled(True)
            ok = "ok" in reply.lower()
            self.test_status.setText(
                "Connected" if ok else f"Replied unexpectedly: {reply[:40]}"
            )
            self.test_status.setStyleSheet(
                "color: #4caf50;" if ok else "color: #ef5350;"
            )

        def failed(error: str) -> None:
            self.test_btn.setEnabled(True)
            self.test_status.setText(f"Failed: {error[:90]}")
            self.test_status.setStyleSheet("color: #ef5350;")

        run_in_thread(work, done, failed)

    def _load_channels(self) -> None:
        from shortube.upload import list_channels

        self.channels_btn.setEnabled(False)
        self.channels_status.setText("Opening browser for YouTube sign-in...")

        def work() -> list[dict]:
            return list_channels()

        def done(channels: list[dict]) -> None:
            self.channels_btn.setEnabled(True)
            self.channel_combo.clear()
            for ch in channels:
                self.channel_combo.addItem(f"{ch['title']} ({ch['id']})", ch["id"])
            self.channels_status.setText(
                f"{len(channels)} channel(s) found" if channels else "No channels found"
            )

        def failed(error: str) -> None:
            self.channels_btn.setEnabled(True)
            self.channels_status.setText(f"Failed: {error[:90]}")

        run_in_thread(work, done, failed)

    def _save(self) -> None:
        payload = {
            "llm_provider": self.provider_combo.currentText(),
            "llm_model": self.model_input.text().strip(),
            "llm_temperature": round(self.temp_slider.value() / 100, 2),
            "ollama_base_url": self.ollama_url.text().strip(),
            "voice_name": self.voice_name.text().strip(),
            "voice_speed": self.voice_speed.value(),
            "voice_volume": self.voice_volume.value(),
            "quality": self.quality_combo.currentData(),
            "video_width": self.width_spin.value(),
            "video_height": self.height_spin.value(),
            "video_fps": self.fps_spin.value(),
            "bumper_duration": self.bumper_spin.value(),
            "transition_duration": self.transition_spin.value(),
            "template": self.template_combo.currentData(),
            "upload_privacy": self.privacy_combo.currentText(),
            "upload_category": self.category_input.text().strip(),
            "upload_language": self.language_input.text().strip(),
            "upload_publish_at": self.publish_at_input.text().strip(),
            "image_provider": self.image_provider_combo.currentText(),
            "media_prefer_videos": self.prefer_videos.isChecked(),
            "background_music_path": self.music_path.text().strip(),
            "music_volume": self.music_volume.value(),
            "duck_threshold": self.duck_threshold.value(),
            "sfx_enabled": self.sfx_enabled.isChecked(),
            "sfx_dir": self.sfx_dir.text().strip(),
            "remotion_concurrency": self.concurrency_spin.value(),
            "caption_font_size": self.caption_font_size.value(),
        }
        discovery = self.discovery_input.text().strip()
        if discovery:
            payload["discovery_model"] = discovery
        groq_key = self.groq_key.text().strip()
        if groq_key and groq_key.lower() != "set":
            payload["groq_api_key"] = groq_key
        openrouter_key = self.openrouter_key.text().strip()
        if openrouter_key and openrouter_key.lower() != "set":
            payload["openrouter_api_key"] = openrouter_key

        channel = self.channel_combo.currentData()
        if channel:
            payload["upload_channel_id"] = channel

        try:
            save_settings(payload)
            self.window.notify("Settings saved")
            self.window.apply_theme()
        except Exception as e:
            self.window.notify(f"Failed to save settings: {e}", 8000)
