#  Time Travel Map Compliance Automation

Este proyecto automatiza la verificación de condiciones de configuración en mapas de tiempo de viaje logístico (Time Travel Map). El script realiza login automático, extrae información de varios sitios, evalúa si se cumplen condiciones clave, genera un Excel con formato y abre un correo personalizado en Outlook con los resultados adjuntos.

---

##  Objetivos

- Extraer configuraciones de Time Travel Map desde interfaz web.
- Evaluar cumplimiento de condiciones clave por site.
- Generar archivo Excel con agrupaciones y formato condicional.
- Preparar resumen en HTML para incluirlo en un correo automático.
- Visualizar un correo Outlook con los datos adjuntos y lista para enviarse.

---

##  Tecnologías utilizadas

- Python 3.9+
- Selenium (automatización de navegador)
- Pandas / OpenPyXL (procesamiento y formato de Excel)
- Win32com (automatización de Outlook)
- pyinputplus (input seguro de PIN)

---

##  Flujo general del script

1. Se autentica en la página mediante Selenium y PIN + Yubikey.
2. Visita el panel TTM de cada site y extrae:
   - Map Built Date
   - Percentile
   - Days of Data
   - End Date
   - Calculate mod-to-mod
   - Bin Type Values (dinámicos)
3. Aplica verificaciones:
   - Coincidencia de valores esperados para cada Bin Type.
   - Que Percentile = 45.
   - Que Calculate mod-to-mod sea True.
   - Que la fecha coincida con el mes actual.
   - Que Days of Data ≥ a lo esperado según el mes.
4. Genera un Excel formateado con agrupación visual.
5. Crea una tabla resumen con los sites que no cumplen condiciones.
6. Inserta esa tabla en un correo Outlook personalizado con template.

---

##  Archivos esperados

- `ct_ob_email.html`: plantilla HTML con marcadores `{body}`, `{site}`, `{report_name}`.
- `TTM_checked.xlsx`: generado automáticamente, contiene los datos formateados.

---

##  Condiciones verificadas

- `Bin Type Values`: deben incluir los siguientes pares clave:
  - DEFAULT:8, LIBRARY:8, LIBRARY-DEEP:8, PALLET-SINGLE:4, PALLET-DOUBLE:2, CASE-FLOW:3
- `Percentile`: debe ser 45
- `Calculate mod-to-mod`: debe ser True
- `Map Built Date`: el mes debe coincidir con el mes actual
- `Days of Data`: debe ser ≥ al umbral mínimo del mes actual

---

##  Ejemplo de tabla resumen en el email

| Site | Compliance |
|------|------------|
| YTH5 | ✅         |
| YTY6 | ❌         |
| DF76 | ✅         |

---

##  Formato del Excel generado

- Agrupación visual entre "Extracted Data" y "Checked Data"
- Colores condicionales:
  - Verde: condiciones cumplidas
  - Rojo: condiciones fallidas
- Ancho de columnas automático

---

