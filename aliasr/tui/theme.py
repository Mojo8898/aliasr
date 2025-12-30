from textual.theme import Theme

from aliasr.core.config import THEME


BUNDLED_THEMES = {
    "aliasr": Theme(
        name="aliasr",
        primary=THEME.primary,
        secondary=THEME.secondary,
        accent=THEME.accent,
        foreground=THEME.foreground,
        background=THEME.background,
        success=THEME.success,
        warning=THEME.warning,
        error=THEME.error,
        surface=THEME.surface,
        panel=THEME.panel,
        dark=THEME.dark,
        variables={
            "block-cursor-text-style": "none",
            "footer-key-foreground": THEME.footer_key_foreground,
        },
    ),
    "hackthebox": Theme(
        name="hackthebox",
        primary="#42A5F5",
        secondary="#EA80FC",
        accent="#4DD0E1",
        foreground="#FFFFFF",
        background="#222B3A",
        success="#C5F467",
        warning="#FFCC5C",
        error="#FF8484",
        surface="#222B3A",
        panel="#222B3A",
        dark=True,
        variables={
            "block-cursor-text-style": "none",
            "footer-key-foreground": "#42A5F5",
        },
    ),
}
