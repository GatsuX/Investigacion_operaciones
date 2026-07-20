#!/usr/bin/env python3
"""
Actualiza Moodle Grader v3.3 a v3.4.

Corrige la extracción de nombres en Prepa en Línea SEP cuando Moodle devuelve
textos de interfaz como "Sin filtro". El problema principal era enviar un
rownum diferente para cada userid; en este tema de Moodle, rownum puede cambiar
el contexto del calificador y hacer que se lea el filtro en lugar del alumno.

Coloca este archivo en la misma carpeta que:
    moodle_grader_corregido_v3_3.py

y ejecuta:
    python corregir_moodle_grader_v3_3_a_v3_4.py

Se generará:
    moodle_grader_corregido_v3_4.py
"""

from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
CANDIDATES = [
    HERE / "moodle_grader_corregido_v3_3.py",
    HERE / "moodle_grader.py",
]

source_path = next((p for p in CANDIDATES if p.exists()), None)
if source_path is None:
    raise SystemExit(
        "No se encontró moodle_grader_corregido_v3_3.py en esta carpeta."
    )

text = source_path.read_text(encoding="utf-8")
original = text

# Actualizar encabezado visible.
text = text.replace(
    "Moodle Universal Grading Script v3.3",
    "Moodle Universal Grading Script v3.4",
    1,
)

# 1) Rechazar textos de controles/filtros que no son nombres.
marker_anchor = "_INVALID_STUDENT_NAME_MARKERS = (\n"
if marker_anchor in text and "    'sin filtro',\n" not in text:
    text = text.replace(
        marker_anchor,
        marker_anchor
        + "    'sin filtro',\n"
        + "    'sin grupo',\n"
        + "    'todos los participantes',\n"
        + "    'mostrar todos',\n",
        1,
    )

# 2) En Prepa SEP debe abrirse cada userid con rownum=0. El rownum no representa
# necesariamente el índice del alumno y puede provocar que Moodle cambie el
# usuario/contexto mostrado.
text, count_rownum = re.subn(
    r"sess, base_url, cmid, userid, rownum=position\s*-\s*1\)",
    "sess, base_url, cmid, userid, rownum=0)",
    text,
    count=1,
)

# 3) Endurecer el método: confirmar que la página individual mencione el userid
# solicitado en su URL final o en controles del calificador. No se aborta si el
# tema no lo incluye, pero se evita usar opciones de select como candidatos.
old_line = "    soup = BeautifulSoup(response.text, 'html.parser')\n"
new_line = """    soup = BeautifulSoup(response.text, 'html.parser')

    # Los textos de opciones y controles (por ejemplo, 'Sin filtro') no deben
    # participar en la detección del nombre.
    for control in soup.find_all(['select', 'option', 'button', 'script', 'style']):
        control.decompose()
"""

# Reemplazar únicamente dentro de _name_from_individual_grader_page.
fn_start = text.find("def _name_from_individual_grader_page(")
fn_end = text.find("\ndef _confirm_student_names(", fn_start)
if fn_start != -1 and fn_end != -1:
    block = text[fn_start:fn_end]
    if old_line in block and "control.decompose()" not in block:
        block = block.replace(old_line, new_line, 1)
        text = text[:fn_start] + block + text[fn_end:]

# 4) Ajustar el respaldo final para evitar candidatos de dos palabras demasiado
# genéricos. Los nombres reales en esta plataforma aparecen junto al correo o en
# encabezados; el respaldo solo debe aceptar al menos tres palabras.
old_fallback = """    for line in soup.get_text('\\n', strip=True).splitlines():
        candidate = _candidate_student_name(line)
        if candidate:
            priority = 0 if candidate == candidate.upper() else 1
            candidates.append((priority, len(candidate.split()), candidate))
"""
new_fallback = """    for line in soup.get_text('\\n', strip=True).splitlines():
        candidate = _candidate_student_name(line)
        if candidate and len(candidate.split()) >= 3:
            priority = 0 if candidate == candidate.upper() else 1
            candidates.append((priority, len(candidate.split()), candidate))
"""
if old_fallback in text:
    text = text.replace(old_fallback, new_fallback, 1)

if text == original:
    raise SystemExit(
        "No se aplicaron cambios. Verifica que el archivo base sea la versión 3.3."
    )

output = HERE / "moodle_grader_corregido_v3_4.py"
output.write_text(text, encoding="utf-8", newline="\n")

# Validación de sintaxis sin ejecutar el menú.
try:
    compile(text, str(output), "exec")
except SyntaxError as exc:
    output.unlink(missing_ok=True)
    raise SystemExit(f"La versión generada no pasó la validación: {exc}")

print()
print("Corrección aplicada correctamente.")
print(f"Archivo creado: {output.name}")
print()
print("Ejecuta ahora:")
print(f"    python .\\{output.name}")
print()
print("Vuelve a generar la plantilla con la opción 1.")
