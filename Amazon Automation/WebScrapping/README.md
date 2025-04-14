#  TNT Hours Automation

Este proyecto automatiza la extracción, procesamiento y envío de reportes sobre los horarios operativos de diferentes centros logísticos (TNT: Time, Node, Transport). Utiliza Selenium para navegar por plataformas internas, Pandas para procesar datos y Outlook para generar correos con los reportes listos para ser enviados.

---

##  Objetivo del proyecto

- Automatizar la navegación por páginas de configuración horaria.
- Extraer las tablas HTML que contienen la configuración de horarios por site.
- Guardar los datos en archivos Excel bien estructurados.
- Leer una lista de destinatarios desde un archivo Excel.
- Generar correos en Outlook con los archivos adjuntos y el cuerpo del mensaje personalizado.

---

##  Tecnologías utilizadas

- Python 3.9+
- Selenium
- Pandas
- pywin32 (Outlook automation)
- XlsxWriter
- webdriver-manager

---

##  Estructura del repositorio

```bash
tnt_hours_automation/
├── src/
│   └── main.py                 # Script principal de automatización
├── input/
│   ├── sites.txt              # Lista de sites a procesar (uno por línea)
│   ├── mailing_list.xlsx      # Lista ficticia de destinatarios por site
│   └── email_template.html    # Plantilla HTML del correo
├── download/                  # Carpeta donde se guardan los Excel generados
├── requirements.txt           # Librerías necesarias
└── README.md                # Este documento
```

---

##  Ejecución del script

```bash
python src/main.py
```

El script:
- Abre Chrome y navega a cada URL de configuración de site.
- Extrae las tablas de horarios (si existen).
- Guarda los archivos Excel en `download/`.
- Genera correos con Outlook y los deja abiertos para revisión manual.

---

##  Plantilla del correo

El correo se genera a partir de un archivo HTML (`input/email_template.html`) que incluye los siguientes marcadores de posición:

```html
{report_name} - Nombre del reporte
target: {site} - Site al que se refiere
{body} - Cuerpo explicativo del mensaje
```

Puedes personalizar esta plantilla para adaptarla al lenguaje de tu organización.

---

##  Archivos de entrada

- `sites.txt`: Lista simple con códigos de site (uno por línea).
- `mailing_list.xlsx`: Archivo con al menos las columnas:
  - `Site`: código del site.
  - `To`: correo electrónico del destinatario.
- `email_template.html`: Plantilla de correo con placeholders.

---

##  Archivos de salida

Generados en `download/` con formato:

```
{site}_TNT_{YYYYMMDD}.xlsx
```

Cada archivo contiene una o varias hojas con tablas extraídas desde la web.

---
