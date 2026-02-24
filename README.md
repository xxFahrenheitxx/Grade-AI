<img src="./assets/logo.png" alt="GradeAI Logo" width="300" />

# GradeAI

AI-powered exam grading assistant for teachers, with a desktop interface and multi-provider AI integration.

## Table of Contents
- [Overview](#overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Run the App](#run-the-app)
- [Build (Executable)](#build-executable)
- [AI Configuration](#ai-configuration)
- [Project Structure](#project-structure)
- [Contributing](#contributing)

## Overview
GradeAI lets you:
- grade exams with AI assistance or manually,
- generate a class-wide exam report (with CSV export and printing).

The project supports `.grd` project archives and stores one grading report per exam copy.

## Features
- Modern desktop UI (PySide6), dark/light theme.
- Project management:
  - create/open/save projects,
  - standard structure: `Exams`, `Solutions`, `Rules`, `Exam Papers`, `Grading Reports`.
- Multi-format document viewing:
  - PDF, images, Word (`.docx`), Excel (`.xlsx`), markdown, text, code.
- Grading:
  - question detection,
  - structured AI grading,
  - AI grading guided by rules written in natural language,
  - manual editing of criteria and points.
- Final grade calculation (`Grade`).
- Exam report:
  - per-student table,
  - per-question success rate,
  - CSV export,
  - A4/A3 landscape printing.
- Multi-provider AI support:
  - Anthropic, OpenAI, Google.

## Tech Stack
- Python
- PySide6 (GUI)
- PyMuPDF
- Pydantic
- Anthropic / OpenAI / Google Generative AI SDKs
- python-docx, openpyxl, Pillow, markdown

## Prerequisites
- Python 3.10+ recommended
- Up-to-date pip
- API key for at least one AI provider:
  - Anthropic, OpenAI, or Google

## Installation
```bash
git clone <REPO_URL>
cd GradeAI

# Optional: virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
# source .venv/bin/activate

pip install -r requirements.txt
```

## Run the App
```bash
python main.py
```

On first launch, configure your API key in `File > Settings`.

## Build (Executable)
You can package the project with PyInstaller.

1. Install PyInstaller:
```bash
pip install pyinstaller
```

2. Build an executable (Windows example):
```bash
pyinstaller ^
  --name GradeAI ^
  --windowed ^
  --noconfirm ^
  --add-data "assets;assets" ^
  --add-data "gradeai/prompts;gradeai/prompts" ^
  main.py
```

The executable is generated in `dist/GradeAI/`.

Notes:
- Adjust `--add-data` depending on OS (`;` on Windows, `:` on Linux/macOS).
- Verify at runtime that prompts and assets are correctly bundled.

## AI Configuration
GradeAI stores user settings in:
- `~/.gradeai/settings.json`

Configurable settings include:
- AI provider (`anthropic`, `openai`, `google`)
- AI model
- API key
- Theme and UI state

## Project Structure
```text
GradeAI/
├── main.py
├── requirements.txt
├── assets/
├── gradeai/
│   ├── app.py
│   ├── constants.py
│   ├── models/
│   ├── services/
│   ├── ui/
│   └── utils/
└── test_exams/
```

## Contributing
Contributions are welcome.

Suggested workflow:
1. Fork the repository
2. Create a feature branch:
```bash
git checkout -b feat/my-feature
```
3. Commit focused and documented changes
4. Open a clear Pull Request (context, impact, screenshots for UI changes)

Best practices:
- keep clear separation between UI/services/models,
- avoid UX regressions in grading workflows,
- include reproduction steps when fixing bugs.
