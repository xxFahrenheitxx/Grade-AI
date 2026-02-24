"""Application settings dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from gradeai.constants import AI_PROVIDERS, THEME_DARK, THEME_LIGHT
from gradeai.models.settings import AppSettings


class SettingsDialog(QDialog):
    """Dialog for editing application settings."""

    def __init__(self, settings: AppSettings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(450)
        self._settings = settings
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # API Configuration
        api_group = QGroupBox("AI Configuration")
        api_layout = QFormLayout(api_group)

        # Provider selection
        self._provider_combo = QComboBox()
        for provider_id, provider_info in AI_PROVIDERS.items():
            self._provider_combo.addItem(provider_info["name"], provider_id)

        # Set current provider
        current_provider_index = 0
        for i in range(self._provider_combo.count()):
            if self._provider_combo.itemData(i) == self._settings.ai_provider:
                current_provider_index = i
                break
        self._provider_combo.setCurrentIndex(current_provider_index)
        self._provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        api_layout.addRow("AI Provider:", self._provider_combo)

        # Model selection
        self._model_combo = QComboBox()
        self._populate_models()
        api_layout.addRow("Model:", self._model_combo)

        # API Key
        self._api_key_edit = QLineEdit()
        self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_edit.setPlaceholderText("Enter your API key...")
        self._api_key_edit.setText(self._settings.api_key)
        api_layout.addRow("API Key:", self._api_key_edit)

        api_note = QLabel("Your API key is stored locally and never shared.")
        api_note.setObjectName("subtitleLabel")
        api_layout.addRow("", api_note)

        layout.addWidget(api_group)

        # Appearance
        appearance_group = QGroupBox("Appearance")
        appearance_layout = QFormLayout(appearance_group)

        self._theme_combo = QComboBox()
        self._theme_combo.addItem("Dark", THEME_DARK)
        self._theme_combo.addItem("Light", THEME_LIGHT)
        current_index = 0 if self._settings.theme == THEME_DARK else 1
        self._theme_combo.setCurrentIndex(current_index)
        appearance_layout.addRow("Theme:", self._theme_combo)

        layout.addWidget(appearance_group)

        layout.addStretch()

        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _populate_models(self) -> None:
        """Populate the model combo box based on selected provider."""
        self._model_combo.clear()
        current_provider = self._provider_combo.currentData()

        if current_provider and current_provider in AI_PROVIDERS:
            models = AI_PROVIDERS[current_provider]["models"]
            for model in models:
                self._model_combo.addItem(model, model)

            # Try to select the current model
            current_model_index = 0
            for i in range(self._model_combo.count()):
                if self._model_combo.itemData(i) == self._settings.ai_model:
                    current_model_index = i
                    break
            self._model_combo.setCurrentIndex(current_model_index)

    def _on_provider_changed(self) -> None:
        """Handle provider selection change."""
        self._populate_models()

    def _on_accept(self) -> None:
        self._settings.api_key = self._api_key_edit.text().strip()
        self._settings.ai_provider = self._provider_combo.currentData()
        self._settings.ai_model = self._model_combo.currentData()
        self._settings.theme = self._theme_combo.currentData()
        self._settings.save()
        self.accept()

    @property
    def settings(self) -> AppSettings:
        return self._settings
