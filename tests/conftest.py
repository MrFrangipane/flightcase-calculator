"""Configuración común de los tests."""

import os
import tempfile

# Los tests nunca escriben en la carpeta de datos real del usuario.
os.environ.setdefault("FLIGHTCASE_DATA_DIR", tempfile.mkdtemp(prefix="flightcase-tests-"))
