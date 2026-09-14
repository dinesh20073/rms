from django.template.loaders.base import Loader as BaseLoader
from django.template import Origin, TemplateDoesNotExist


class Loader(BaseLoader):
    """
    Placeholder template loader kept for backward compatibility.
    In production, templates are served from the filesystem via the standard
    Django template loaders. The embedded_templates.py fallback has been removed.
    """
    def get_contents(self, origin):
        raise TemplateDoesNotExist(origin.template_name)

    def get_template_sources(self, template_name):
        # Yield nothing — filesystem loaders handle everything now
        return iter([])
