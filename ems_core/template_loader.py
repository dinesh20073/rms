"""
Embedded Template Loader for Django.
Loads templates directly from the in-memory EMBEDDED_TEMPLATES dictionary.
Serves as an airtight fallback for serverless deployments (such as Vercel)
where non-python files in the file system may be excluded or unreachable.
"""
from django.template.loaders.base import Loader as BaseLoader
from django.template import Origin, TemplateDoesNotExist


class EmbeddedTemplateLoader(BaseLoader):
    """
    Django template loader that serves templates from ems_core.embedded_templates.
    """

    def get_contents(self, origin):
        try:
            from ems_core.embedded_templates import EMBEDDED_TEMPLATES
        except ImportError:
            raise TemplateDoesNotExist(origin.name)

        # Normalize key
        clean_name = origin.name
        if clean_name.startswith('embedded:'):
            clean_name = clean_name[len('embedded:'):]
        clean_name = clean_name.replace('\\', '/').strip('/')

        if clean_name in EMBEDDED_TEMPLATES:
            return EMBEDDED_TEMPLATES[clean_name]

        template_name = getattr(origin, 'template_name', '').replace('\\', '/').strip('/')
        if template_name in EMBEDDED_TEMPLATES:
            return EMBEDDED_TEMPLATES[template_name]

        for k, v in EMBEDDED_TEMPLATES.items():
            norm_k = k.replace('\\', '/').strip('/')
            if norm_k == clean_name or norm_k.endswith('/' + clean_name) or clean_name.endswith('/' + norm_k):
                return v

        raise TemplateDoesNotExist(origin.name)

    def get_template_sources(self, template_name):
        try:
            from ems_core.embedded_templates import EMBEDDED_TEMPLATES
        except ImportError:
            return

        norm_name = template_name.replace('\\', '/').strip('/')

        if norm_name in EMBEDDED_TEMPLATES:
            yield Origin(
                name=f"embedded:{norm_name}",
                template_name=norm_name,
                loader=self,
            )
            return

        # Check for suffix or prefix matches
        found = False
        for k in EMBEDDED_TEMPLATES:
            norm_k = k.replace('\\', '/').strip('/')
            if norm_k == norm_name or norm_k.endswith('/' + norm_name) or norm_name.endswith('/' + norm_k):
                yield Origin(
                    name=f"embedded:{norm_k}",
                    template_name=norm_name,
                    loader=self,
                )
                found = True
                break
