import flet as ft

BG = "#0B0D12"
SURFACE = "#151822"
SURFACE_ALT = "#1D2130"
BORDER = "#2A2F41"
TEXT_PRIMARY = "#F2F3F7"
TEXT_MUTED = "#8B90A3"
ACCENT = "#6C8CFF"
SUCCESS = "#4ADE80"
WARNING = "#FBBF24"
DANGER = "#F87171"


def theme() -> ft.Theme:
    return ft.Theme(
        color_scheme_seed=ACCENT,
        color_scheme=ft.ColorScheme(
            primary=ACCENT,
            surface=SURFACE,
            on_surface=TEXT_PRIMARY,
        ),
    )


def configure_page(page: ft.Page) -> None:
    page.title = "TenThousand"
    page.theme_mode = ft.ThemeMode.DARK
    page.theme = theme()
    page.bgcolor = BG
    page.padding = 0
    page.fonts = {}
