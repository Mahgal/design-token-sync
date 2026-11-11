"""design-token-sync: design-tokens JSON -> CSS custom properties + Tailwind v4 @theme."""

from .tokens import Token, ValidationReport, flatten_tokens, load_tokens

__all__ = ["Token", "ValidationReport", "flatten_tokens", "load_tokens"]
__version__ = "0.1.0"
