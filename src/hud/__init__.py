"""Neiro-NQ-Quant HUD / Tactical Terminal Module."""

def __getattr__(name: str):
    if name in ("build_plotly_terminal", "generate_html_terminal", "build_and_export_dashboard"):
        from .html_dashboard import build_plotly_terminal, generate_html_terminal, build_and_export_dashboard
        mapping = {
            "build_plotly_terminal": build_plotly_terminal,
            "generate_html_terminal": generate_html_terminal,
            "build_and_export_dashboard": build_and_export_dashboard,
        }
        return mapping[name]
    if name in ("render_neiro_orderflow_component",):
        from .neiro_terminal import render_neiro_orderflow_component
        return render_neiro_orderflow_component
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "build_plotly_terminal",
    "generate_html_terminal",
    "build_and_export_dashboard",
    "render_neiro_orderflow_component",
]
