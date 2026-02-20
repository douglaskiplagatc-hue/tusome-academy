# template_debugger.py

from flask import template_rendered
import jinja2

def debug_template_context(app):
    """
    Logs missing variables in Jinja templates during rendering.
    Only use in development mode.
    """
    def record(sender, template, context, **extra):
        # Extract template filename
        template_name = template.name or "[inline template]"
        print(f"\n🧩 [Template Debug] Rendering: {template_name}")

        # Detect Jinja Undefined variables
        for key, value in context.items():
            if isinstance(value, jinja2.Undefined):
                print(f"⚠️  Undefined variable detected in template: {key}")

    template_rendered.connect(record, app)
