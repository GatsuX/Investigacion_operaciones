#!/usr/bin/env python3
"""
Genera una copia completa corregida de Moodle Universal Grading Script v3.2.

Corrección principal:
- En Prepa en Línea SEP confirma el nombre de cada estudiante abriendo su
  pantalla individual de calificación mediante el userid.
- Evita guardar como nombre textos como "Actualizar calificación", botones,
  lemas o campos personalizados del perfil.

Uso:
    1. Coloca este archivo en la misma carpeta del Moodle Grader original.
    2. Ejecuta:
           python crear_moodle_grader_corregido_v3_3.py
    3. Se creará:
           moodle_grader_corregido_v3_3.py
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path


OUTPUT_NAME = "moodle_grader_corregido_v3_3.py"


def find_source() -> Path:
    """Localiza el Moodle Grader original en la carpeta actual."""
    here = Path(__file__).resolve()

    preferred = [
        "moodle_grader.py",
        "moodle_grader(2).py",
        "moodle_grader(1).py",
        "moodle_grader_corregido_v3_2_google_sso.py",
    ]

    for name in preferred:
        candidate = here.with_name(name)
        if candidate.exists() and candidate.resolve() != here:
            return candidate

    candidates = sorted(
        path for path in here.parent.glob("moodle_grader*.py")
        if path.resolve() != here
        and path.name != OUTPUT_NAME
        and "crear_moodle_grader_corregido" not in path.name
    )

    if candidates:
        return candidates[0]

    raise FileNotFoundError(
        "No se encontró el Moodle Grader original en esta carpeta. "
        "Coloca aquí moodle_grader.py o moodle_grader(2).py."
    )


INSERTED_CODE = r'''

# ══════════════════════════════════════════════════════════
#  CORRECCIÓN v3.3 — NOMBRES DE ESTUDIANTES EN PREPA SEP
# ══════════════════════════════════════════════════════════

import unicodedata


_INVALID_STUDENT_NAME_MARKERS = (
    'actualizar calificacion',
    'actualizar calificación',
    'calificar',
    'ver entrega',
    'seleccionar usuario',
    'select user',
    'cambiar usuario',
    'guardar cambios',
    'guardar y mostrar siguiente',
    'no calificado',
    'enviado para calificar',
    'para llegas a la meta',
    'para llegar a la meta',
    'actividad integradora',
    'limites y aplicacion',
    'límites y aplicación',
    'modulo 18',
    'módulo 18',
    'curso',
    'tarea',
    'entrega',
    'calificacion',
    'calificación',
    'fecha de entrega',
    'ver todos los envios',
    'ver todos los envíos',
)


def _fold_student_text(value):
    """Normaliza acentos y mayúsculas para comparar textos visibles."""
    text = re.sub(r'\s+', ' ', str(value or '')).strip()
    normalized = unicodedata.normalize('NFKD', text)
    normalized = ''.join(
        char for char in normalized
        if not unicodedata.combining(char)
    )
    return normalized.casefold()


def _looks_like_real_student_name(value):
    """Valida que el texto tenga una estructura razonable de nombre completo."""
    name = re.sub(r'\s+', ' ', str(value or '')).strip(' -|')
    folded = _fold_student_text(name)
    words = [word for word in name.split() if word]

    if len(words) < 2 or len(words) > 8:
        return False
    if any(marker in folded for marker in _INVALID_STUDENT_NAME_MARKERS):
        return False
    if any(char.isdigit() for char in name):
        return False
    if any(symbol in name for symbol in ('@', ':', '/', '\\', '=', '[', ']')):
        return False

    alphabetic = 0
    for word in words:
        cleaned = word.strip(".,;()_-'")
        if not cleaned:
            continue
        letters = [char for char in cleaned if char.isalpha()]
        if not letters:
            return False
        if len(letters) / max(1, len(cleaned)) < 0.70:
            return False
        alphabetic += 1

    return alphabetic >= 2


def _candidate_student_name(value):
    """Limpia etiquetas frecuentes antes de validar un nombre."""
    text = re.sub(r'\s+', ' ', str(value or '')).strip()
    text = re.sub(
        r'^(?:nombre|estudiante|alumno|alumna|usuario)\s*:\s*',
        '',
        text,
        flags=re.IGNORECASE,
    ).strip()
    text = re.sub(
        r'^(?:imagen|foto|picture)\s+(?:de|of)\s+',
        '',
        text,
        flags=re.IGNORECASE,
    ).strip()
    return text if _looks_like_real_student_name(text) else ''


def _name_from_individual_grader_page(sess, base_url, cmid, userid, rownum=0):
    """Obtiene el nombre real desde la pantalla individual action=grader."""
    url = (
        f"{base_url}/mod/assign/view.php?id={cmid}"
        f"&rownum={rownum}&action=grader&userid={userid}"
    )

    try:
        response = sess.get(url, timeout=30, allow_redirects=True)
    except Exception:
        return ''

    if (response.status_code != 200 or '/login/' in str(response.url) or
            _looks_like_login_page(response.text, response.url)):
        return ''

    soup = BeautifulSoup(response.text, 'html.parser')

    # Selectores usados por Moodle clásico, temas personalizados y el
    # calificador individual de Prepa en Línea SEP.
    selectors = (
        '[data-region="user-fullname"]',
        '[data-region="user-info"] .fullname',
        '.useridentification .fullname',
        '.grading-navigation .fullname',
        '.submissionstatustable .fullname',
        '.user-fullname',
        '.userfullname',
        '.fullname',
        '.page-context-header .page-header-headings h2',
        '.page-context-header .page-header-headings h1',
        '#page-header .page-header-headings h2',
        '#page-header .page-header-headings h1',
        '.page-context-header h2',
        '.page-context-header h1',
    )

    for selector in selectors:
        for node in soup.select(selector):
            candidate = _candidate_student_name(node.get_text(' ', strip=True))
            if candidate:
                return candidate

    # En Prepa SEP el correo institucional suele estar inmediatamente debajo
    # del nombre. Se buscan primero los elementos anteriores al correo.
    email_pattern = re.compile(
        r'[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}',
        flags=re.IGNORECASE,
    )

    for email_text in soup.find_all(string=email_pattern):
        email_node = getattr(email_text, 'parent', None)
        if email_node is None:
            continue

        # Hermanos anteriores del correo.
        sibling = email_node.previous_sibling
        checked = 0
        while sibling is not None and checked < 10:
            checked += 1
            if hasattr(sibling, 'get_text'):
                raw = sibling.get_text(' ', strip=True)
            else:
                raw = str(sibling).strip()
            candidate = _candidate_student_name(raw)
            if candidate:
                return candidate
            sibling = getattr(sibling, 'previous_sibling', None)

        # Elementos previos cercanos dentro del mismo bloque visual.
        for node in email_node.find_all_previous(
                ['h1', 'h2', 'h3', 'h4', 'strong', 'span', 'div'], limit=25):
            candidate = _candidate_student_name(node.get_text(' ', strip=True))
            if candidate:
                return candidate

        # Hijos de los ancestros inmediatos.
        ancestors = []
        parent = email_node.parent
        while parent is not None and len(ancestors) < 5:
            ancestors.append(parent)
            parent = getattr(parent, 'parent', None)
        for ancestor in ancestors:
            for node in ancestor.find_all(
                    ['h1', 'h2', 'h3', 'h4', 'strong', 'span', 'div'],
                    recursive=True):
                raw = node.get_text(' ', strip=True)
                if email_pattern.search(raw):
                    continue
                candidate = _candidate_student_name(raw)
                if candidate:
                    return candidate

    # Fotografías de usuario: algunos temas guardan el nombre en alt/title.
    for image in soup.find_all('img'):
        for attr in ('alt', 'title'):
            candidate = _candidate_student_name(image.get(attr, ''))
            if candidate:
                return candidate

    # Último respaldo: líneas visibles. Se priorizan nombres completamente en
    # mayúsculas, como los encabezados mostrados por Prepa en Línea SEP.
    candidates = []
    for line in soup.get_text('\n', strip=True).splitlines():
        candidate = _candidate_student_name(line)
        if candidate:
            priority = 0 if candidate == candidate.upper() else 1
            candidates.append((priority, len(candidate.split()), candidate))

    if candidates:
        candidates.sort(key=lambda item: (item[0], item[1], len(item[2])))
        return candidates[0][2]

    return ''


def _confirm_student_names(sess, base_url, cmid, students):
    """Confirma nombres por userid cuando el tema de Moodle no es confiable."""
    from urllib.parse import urlparse

    if not students:
        return students

    host = (urlparse(base_url).hostname or '').casefold()
    is_prepa_sep = 'prepaenlinea.sep.gob.mx' in host
    has_invalid = any(
        not _looks_like_real_student_name(student.get('name', ''))
        for student in students
    )

    # En otros Moodle se conserva el flujo rápido si todos los nombres parecen
    # correctos. En Prepa SEP siempre se confirma cada userid.
    if not is_prepa_sep and not has_invalid:
        return students

    print()
    step('Confirmando nombres desde la pantalla individual de Moodle...')
    total = len(students)
    confirmed_count = 0
    unresolved = []

    for position, student in enumerate(students, 1):
        userid = str(student.get('userid', '')).strip()
        confirmed = _name_from_individual_grader_page(
            sess, base_url, cmid, userid, rownum=position - 1)

        if confirmed:
            student['name'] = confirmed
            confirmed_count += 1
        elif not _looks_like_real_student_name(student.get('name', '')):
            student['name'] = f'Alumno userid {userid}'
            unresolved.append(userid)

        print(
            f"\r     {position}/{total} estudiantes revisados",
            end='',
            flush=True,
        )

    print()
    ok(f'Nombres confirmados: {confirmed_count} de {total}.')
    if unresolved:
        warn(
            'No se pudo confirmar el nombre de estos userid: ' +
            ', '.join(unresolved)
        )
        warn('Sus filas se marcaron como "Alumno userid ..." para evitar textos falsos.')

    return students


def get_students(sess, base_url, cmid):
    """Obtiene los alumnos y confirma sus nombres cuando sea necesario."""
    students = _get_students_unconfirmed(sess, base_url, cmid)
    return _confirm_student_names(sess, base_url, cmid, students)
'''


def build_corrected(source: str) -> str:
    """Inserta la corrección conservando todas las funciones originales."""
    source = source.replace(
        "Moodle Universal Grading Script v3.2",
        "Moodle Universal Grading Script v3.3",
    )

    start_marker = "def get_students(sess, base_url, cmid):"
    end_marker = "\ndef _compact_text(value):"

    start = source.find(start_marker)
    if start < 0:
        raise ValueError("No se encontró la función get_students().")

    end = source.find(end_marker, start)
    if end < 0:
        raise ValueError("No se encontró el final de get_students().")

    original_block = source[start:end]
    renamed_block = original_block.replace(
        "def get_students(sess, base_url, cmid):",
        "def _get_students_unconfirmed(sess, base_url, cmid):",
        1,
    )

    corrected = source[:start] + renamed_block + INSERTED_CODE + source[end:]

    # Validación de sintaxis antes de guardar.
    ast.parse(corrected)
    return corrected


def main() -> int:
    print("\nMoodle Grader — generador de corrección v3.3\n")

    try:
        source_path = find_source()
        original = source_path.read_text(encoding="utf-8")
        corrected = build_corrected(original)
    except (OSError, ValueError, SyntaxError) as exc:
        print(f"ERROR: {exc}")
        return 1

    output_path = source_path.with_name(OUTPUT_NAME)
    output_path.write_text(corrected, encoding="utf-8", newline="\n")

    print(f"Archivo original : {source_path.name}")
    print(f"Archivo corregido: {output_path.name}")
    print("\nLa sintaxis fue validada correctamente.")
    print("Ejecuta ahora:")
    print(f"    python {output_path.name}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
