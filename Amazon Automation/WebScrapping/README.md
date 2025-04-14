# 📦 TNT Hours Automation Script

Este proyecto automatiza el proceso de extracción, validación y envío de informes sobre horarios de operación (TNT Hours) de distintos centros logísticos.

## 🎯 Objetivo

- Automatizar la autenticación y navegación mediante Selenium.
- Extraer dinámicamente tablas HTML con configuraciones horarias por site.
- Guardar los datos en Excel, formateados y estructurados por site.
- Generar y abrir correos personalizados en Outlook con archivos adjuntos listos para enviar.

## 🛠 Tecnologías utilizadas

- Python 3.9+
- Selenium
- Pandas
- Outlook (vía `pywin32`)
- Jupyter / VS Code

## 📁 Estructura del proyecto

tnt_hours_automation/ ├── src/main.py # Código principal ├── input/sites.txt # Lista de sites a procesar ├── input/mailing_list.xlsx # Archivo simulado con lista de correos (no real) ├── input/email_template.html # Plantilla de email con marcador {body} ├── download/ # Archivos Excel generados ├── requirements.txt # Dependencias └── README.md
