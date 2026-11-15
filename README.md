# Calculadora de Flightcases

Herramienta de escritorio de diseño y cálculo (CAD/CAM) hecha con Python, PySide6 y OpenGL para agilizar el diseño, el cálculo y la fabricación de flightcases y baúles de gira a medida.

![Captura 3D](screenshot-3d.jpg)

![Captura 2D](screenshot-2d.jpg)

---

## Funciones

- **Cálculo preciso de materiales, costo y peso**:
  - Calcula automáticamente las medidas exactas de corte, superficies y cantidades de los paneles de madera (laterales, tapa, piso, techo) y de los perfiles de aluminio (ángulos esquineros y perfiles de cierre de tapa).
  - Calcula la superficie total de madera ($m^2$), el peso estimado ($kg$), el costo total estimado de material ($€$) y la cantidad de placas estándar de $2440 \times 1220\text{ mm}$.
- **Biblioteca de maderas y materiales propios**:
  - Materiales predefinidos cargados desde un JSON (multilaminado de abedul de 4 a 18 mm, abedul texturado hexagonal, álamo liviano y paneles Astroboard / Con-Pearl).
  - Carga y sincroniza automáticamente el espesor, la densidad ($\text{kg/m}^3$) y el precio por unidad de superficie ($€/\text{m}^2$).
  - Soporte completo para materiales personalizados.
- **Visor 3D interactivo con OpenGL**:
  - Navegación 3D completa (órbita, desplazamiento y zoom) con renderizado acelerado por hardware, en alambre y sólido con antialiasing.
  - Control de vista explotada con cotas automáticas de cada panel.
  - Simulación de apertura de la tapa con lado de bisagra a elección (trasero, delantero, izquierdo, derecho) y giro de 0° a 180°.
  - Dibujo dinámico de los divisores internos y resaltado sincronizado entre la vista 3D y las tablas de cortes.
  - Soporta tanto la construcción con tapa separada como la de tapa cortada a mano (caja cerrada de 6 caras), con la línea de corte marcada.
- **Planos 2D de los paneles de madera (SVG)**:
  - Genera planos de corte vectoriales de alto contraste, listos para imprimir.
  - Vista 2D interactiva con desplazamiento y zoom suaves.
  - Exportación a SVG con un clic, lista para imprimir o preparar el corte láser/CNC.
- **Gestión dinámica de compartimentos y divisores**:
  - Configuración de divisores internos en los ejes X e Y con recálculo en tiempo real.
  - Distribución automática en partes iguales o ancho personalizado por compartimento.
  - El espesor de los divisores se sincroniza automáticamente con el material de madera elegido.
- **Listado de materiales y listas de cortes**:
  - Tablas detalladas de cortes de madera y de perfiles de aluminio con desplazamiento suave.
  - Exportación del listado completo de materiales a CSV para el taller y los pedidos a proveedores.
- **Presupuesto, herrajes y peso total**:
  - Catálogo editable de herrajes y perfiles (`resources/hardware.json` y `resources/alu_profiles.json`) con precio, peso y largo de barra.
  - Conteo automático de esquineros, cierres, asas, bisagras, ruedas, tazas de apilado y remaches según el tamaño y las opciones de la caja.
  - Desglose de precio: madera, perfiles, herrajes, consumibles, mano de obra (horas fijas + horas por m²), margen e IVA. Se guarda con cada proyecto.
- **Optimización de corte**:
  - Despiece real de los paneles en placas (corte de guillotina, grosor de sierra, saneado de borde y opción de no girar por la veta).
  - Reparto de los cortes de perfil en barras con su sobrante.
- **Paquete de producción en un clic** (*Archivo → Exportar paquete de producción*):
  - DXF por espesor con las placas despiezadas (capas PLACA, CORTE y ETIQUETAS) para CNC o sierra.
  - Hoja de montaje en PDF para el taller (sin precios) y presupuesto interno en PDF (con precios).
  - Listado de materiales en CSV y planos de paneles en SVG.
- **Gestión de proyectos e interfaz cómoda**:
  - Guardado y apertura de archivos de proyecto `.fcproj`, con restauración automática del estado de la ventana y del último proyecto.
  - Acceso rápido a los proyectos abiertos recientemente.
  - Tema oscuro pensado para el taller, con un panel de configuración fijo y ordenado.

---

## Requisitos

- Python >= 3.14
- Sistemas operativos: Windows, macOS, Linux

### Dependencias principales

- `PySide6`: interfaz de escritorio moderna basada en Qt
- `PyOpenGL`: renderizado 3D acelerado por hardware (alambre y superficies sólidas)
- `numpy`: transformaciones geométricas 3D rápidas con vectores y matrices
- `pytest`: tests automáticos

---

## Primeros pasos

### Instalar en Windows o Mac (sin Python)

Los instaladores se generan solos en GitHub (*Actions → Instaladores*). Para publicar una versión, creá una etiqueta `vX.Y.Z`: aparecen en *Releases*.

- **Windows**: `FlightcaseCalculator-X.Y.Z-Windows-Instalador.exe`. Si aparece «Windows protegió su PC», tocá *Más información → Ejecutar de todas formas* (el instalador todavía no está firmado).
- **Mac**: `…-macOS-AppleSilicon.dmg` (M1 o más nuevo) o `…-macOS-Intel.dmg`. Arrastrá la app a Aplicaciones. La primera vez, clic derecho sobre la app → *Abrir* (todavía no está firmada por Apple).

Los catálogos que edites (maderas, herrajes, perfiles) se guardan en tu carpeta de usuario (`%APPDATA%\FlightcaseCalculator` en Windows, `~/Library/Application Support/FlightcaseCalculator` en Mac), así que no se pierden al actualizar.

### 1. Instalación para desarrollo

Cloná o descargá el repositorio e instalá las dependencias:

```bash
# Con uv (recomendado)
uv sync

# O con pip
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux / macOS:
source .venv/bin/activate

pip install -e .
```

### 2. Ejecutar la aplicación

- **Acceso directo en Windows**: hacé doble clic en `run.cmd` o ejecutá:
  ```cmd
  run.cmd
  ```
- **Desde la terminal**:
  ```bash
  python main.py
  # o con uv
  uv run python main.py
  ```

### 3. Ejecutar los tests

Para correr todos los tests:

```bash
uv run pytest
# o con el entorno virtual activado:
pytest
```

---

## Traducción

La interfaz, los mensajes, las exportaciones (CSV y SVG) y este README están en español. Los nombres de piezas, notas y etiquetas que genera el modelo se siguen calculando en inglés internamente (se usan para agrupar piezas, resaltar en 3D y guardar proyectos) y se traducen al mostrarlos o exportarlos mediante `flightcase/i18n.py`. Los proyectos `.fcproj` guardados con la versión en inglés se abren sin cambios.
