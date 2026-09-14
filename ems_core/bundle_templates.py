#!/usr/bin/env python
"""
Bundle all templates in templates/ into an embedded Python dictionary in ems_core/embedded_templates.py.
This guarantees 100% template availability on serverless platforms (like Vercel) even if non-code files
are not copied to the lambda filesystem.
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates')
OUTPUT_FILE = os.path.join(BASE_DIR, 'ems_core', 'embedded_templates.py')


def bundle():
    templates = {}
    if not os.path.isdir(TEMPLATES_DIR):
        print(f"[bundle_templates] Warning: {TEMPLATES_DIR} does not exist.")
        return

    count = 0
    for root, dirs, files in os.walk(TEMPLATES_DIR):
        for f in files:
            if f.endswith('.html'):
                abs_path = os.path.join(root, f)
                rel_path = os.path.relpath(abs_path, TEMPLATES_DIR).replace('\\', '/')
                with open(abs_path, 'r', encoding='utf-8') as fh:
                    content = fh.read()
                templates[rel_path] = content
                count += 1

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as out:
        out.write('"""\nAuto-generated in-memory template bundle.\nGenerated for fail-safe serverless execution on Vercel.\n"""\n\n')
        out.write('EMBEDDED_TEMPLATES = {\n')
        for key, val in sorted(templates.items()):
            # Use repr for safe escaping of all newlines, quotes, etc.
            out.write(f"    {repr(key)}: {repr(val)},\n")
        out.write('}\n')

    print(f"[bundle_templates] Successfully bundled {count} templates into {OUTPUT_FILE}")


if __name__ == '__main__':
    bundle()
