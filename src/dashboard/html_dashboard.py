"""Alias for src.hud.html_dashboard for backward and cross-module compatibility."""
from src.hud.html_dashboard import (
    clean_val,
    load_options_dataset,
    build_plotly_terminal,
    generate_html_terminal,
    build_and_export_dashboard,
    main,
)

__all__ = [
    "clean_val",
    "load_options_dataset",
    "build_plotly_terminal",
    "generate_html_terminal",
    "build_and_export_dashboard",
    "main",
]

if __name__ == "__main__":
    main()
