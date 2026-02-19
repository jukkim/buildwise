"""EMS template renderer.

Loads Jinja2 .j2 templates from the EMS template directory
and renders them with building-specific context variables.
"""

from __future__ import annotations

import logging
from pathlib import Path

from jinja2 import FileSystemLoader, TemplateNotFound
from jinja2.sandbox import SandboxedEnvironment

logger = logging.getLogger(__name__)

# Default path to energyplus_sim EMS templates
_DEFAULT_TEMPLATE_DIR = Path(__file__).parent.parent.parent.parent / "config" / "ems_templates"


class EMSRenderer:
    """Stateful EMS template renderer with caching."""

    def __init__(self, template_dir: Path | None = None) -> None:
        self.template_dir = template_dir or _DEFAULT_TEMPLATE_DIR
        self._env: SandboxedEnvironment | None = None

    @property
    def env(self) -> SandboxedEnvironment:
        if self._env is None:
            if not self.template_dir.exists():
                raise FileNotFoundError(f"EMS template directory not found: {self.template_dir}")
            self._env = SandboxedEnvironment(
                loader=FileSystemLoader(str(self.template_dir)),
                keep_trailing_newline=True,
                trim_blocks=True,
                lstrip_blocks=True,
            )
        return self._env

    def render(self, template_name: str, context: dict) -> str:
        """Render a single EMS template."""
        try:
            tmpl = self.env.get_template(template_name)
            return tmpl.render(**context)
        except TemplateNotFound:
            logger.error("EMS template not found: %s", template_name)
            return f"! Template not found: {template_name}\n"
        except Exception as exc:
            logger.error("EMS render error for %s: %s", template_name, exc)
            return f"! Render error for {template_name}: {exc}\n"

    def render_multiple(self, template_names: list[str], context: dict) -> str:
        """Render multiple EMS templates and concatenate."""
        parts = []
        for name in template_names:
            rendered = self.render(name, context)
            parts.append(f"! === EMS: {name} ===\n{rendered}")
        return "\n\n".join(parts)

    def list_templates(self) -> list[str]:
        """List all available .j2 templates."""
        if not self.template_dir.exists():
            return []
        return sorted(p.name for p in self.template_dir.glob("*.j2"))
