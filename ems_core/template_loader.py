from django.template.loaders.base import Loader as BaseLoader
from django.template import Origin, TemplateDoesNotExist
try:
    from ems_core.embedded_templates import EMBEDDED_TEMPLATES
except ImportError:
    EMBEDDED_TEMPLATES = {}

class Loader(BaseLoader):
    """
    Fail-safe embedded template loader that guarantees all templates are available
    in serverless environments (e.g. AWS Lambda / Vercel) even when the filesystem
    strips non-code assets.
    """
    def get_contents(self, origin):
        name = origin.template_name.replace('\\', '/').strip('/')
        if name in EMBEDDED_TEMPLATES:
            return EMBEDDED_TEMPLATES[name]
        
        # Suffix / fuzzy match
        for k, v in EMBEDDED_TEMPLATES.items():
            clean_k = k.replace('\\', '/').strip('/')
            if clean_k == name or clean_k.endswith('/' + name) or name.endswith('/' + clean_k):
                return v

        raise TemplateDoesNotExist(origin.template_name)

    def get_template_sources(self, template_name):
        name = template_name.replace('\\', '/').strip('/')
        yield Origin(
            name=f"embedded:{name}",
            template_name=name,
            loader=self,
        )
