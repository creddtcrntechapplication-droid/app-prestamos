"""Protege el HTML inicial de Streamlit antes de servirlo; ejecutar al construir."""
from pathlib import Path
import re


def spanish_shell(source):
    """No modifica React ni intercepta errores: declara el idioma de la interfaz."""
    def root(match):
        attrs = re.sub(r'\s+(?:lang|translate)\s*=\s*[\"\'][^\"\']*[\"\']', '', match.group(1), flags=re.I)
        return '<html' + attrs + ' lang="es" translate="no">'
    result, count = re.subn(r'<html\b([^>]*)>', root, source, count=1, flags=re.I)
    if count != 1 or not re.search(r'<head\b[^>]*>', result, flags=re.I):
        raise ValueError('No se encontró la plantilla HTML esperada de Streamlit.')
    if not re.search(r'<meta\b[^>]*name=[\"\']google[\"\'][^>]*content=[\"\']notranslate[\"\']', result, flags=re.I):
        result = re.sub(r'(<head\b[^>]*>)', r'\1<meta name="google" content="notranslate">', result, count=1, flags=re.I)
    return result


if __name__ == '__main__':
    import streamlit
    template = Path(streamlit.__file__).resolve().parent / 'static' / 'index.html'
    original = template.read_text(encoding='utf-8')
    protected = spanish_shell(original)
    if protected != original:
        template.write_text(protected, encoding='utf-8')
    print('CREDDT: plantilla inicial en español y protegida de traducción automática.')
