"""Application-wide constants."""

APP_NAME = "Grade AI"
APP_VERSION = "1.0.20260224"
APP_ORGANIZATION = "GradeAI"

# AI Models and Providers
AI_PROVIDERS = {
    "anthropic": {
        "name": "Anthropic (Claude)",
        "models": [
            "claude-sonnet-4-6",
            "claude-opus-4-6",
            "claude-haiku-4-5-20251001",
        ],
    },
    "openai": {
        "name": "OpenAI (ChatGPT)",
        "models": [
            "gpt-5-mini-2025-08-07",
            "gpt-4o",
            "gpt-4o-mini",
        ],
    },
    "google": {
        "name": "Google (Gemini)",
        "models": [
            "gemini-3-flash-preview",
            "gemini-2.0-flash-exp",
            "gemini-1.5-pro",
        ],
    },
}

# Default AI configuration
DEFAULT_AI_PROVIDER = "anthropic"
DEFAULT_AI_MODEL = "claude-sonnet-4-6"
AI_MAX_TOKENS = 8192

# Project structure folder names
EXAMS_DIR = "Exams"
SOLUTIONS_DIR = "Solutions"
RULES_DIR = "Rules"
EXAM_PAPERS_DIR = "Exam Papers"
GRADING_REPORTS_DIR = "Grading Reports"
PROMPTS_DIR = "Prompts"

# Project file extension
PROJECT_EXTENSION = ".grd"
PROJECT_FILTER = f"Grade AI Project (*{PROJECT_EXTENSION})"

# Project metadata filename
PROJECT_META_FILE = "project.json"

# Settings keys
SETTINGS_API_KEY = "api_key"
SETTINGS_THEME = "theme"
SETTINGS_RECENT_PROJECTS = "recent_projects"
SETTINGS_WINDOW_GEOMETRY = "window_geometry"
SETTINGS_WINDOW_STATE = "window_state"
SETTINGS_SPLITTER_SIZES = "splitter_sizes"

# Theme names
THEME_DARK = "dark"
THEME_LIGHT = "light"
DEFAULT_THEME = THEME_DARK

# Supported file extensions by category
PDF_EXTENSIONS = {".pdf"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp"}
WORD_EXTENSIONS = {".docx"}
EXCEL_EXTENSIONS = {".xlsx"}
CODE_EXTENSIONS = {".py", ".js", ".sql", ".html", ".css", ".java", ".c", ".cpp", ".h", ".json", ".xml", ".yaml", ".yml"}
MARKDOWN_EXTENSIONS = {".md", ".markdown"}
TEXT_EXTENSIONS = {".txt", ".log", ".csv", ".ini", ".cfg"}

ALL_VIEWABLE_EXTENSIONS = (
    PDF_EXTENSIONS | IMAGE_EXTENSIONS | WORD_EXTENSIONS | EXCEL_EXTENSIONS
    | CODE_EXTENSIONS | MARKDOWN_EXTENSIONS | TEXT_EXTENSIONS
)

# Zoom limits
ZOOM_MIN = 0.25
ZOOM_MAX = 4.0
ZOOM_STEP = 0.1
ZOOM_DEFAULT = 0.6

# Max recent projects
MAX_RECENT_PROJECTS = 10
