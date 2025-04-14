# 🧾 Ticket Categorization Tool (Pattern Matching)

Este proyecto automatiza la clasificación de tickets a partir de su contenido textual, aplicando técnicas de búsqueda por patrones (regex) para identificar causas raíz y facilitar el análisis de incidencias.

---

## 🚀 Objetivo

- Automatizar el análisis y categorización de tickets de soporte.
- Identificar causas comunes mediante expresiones regulares.
- Generar reportes estructurados por categoría y ticket.

---

## 🛠 Tecnologías utilizadas

- Python (3.9+)
- Regex (`re`)
- Pandas
- Archivos planos `.txt`
- Automatización para generación de informes `.csv`

---

## 🔍 ¿Cómo funciona?

1. **Lee una lista de tickets objetivo** desde un archivo `.txt`.
2. **Procesa un documento grande de comentarios**, localizando cada ticket y analizando su contenido.
3. **Busca patrones predefinidos** en función de categorías relevantes como:
   - `Max_Capacity_Express_Services`
   - `Delivery_Area_Restrictions`
   - `Capacity_Details`
4. **Asigna una o varias categorías** por ticket.
5. **Genera estadísticas y exporta resultados** en formato CSV.

---

## 📊 Resultados generados

- `tickets_by_category.csv`: Vista por categoría, incluyendo los patrones detectados.
- `tickets_summary.csv`: Vista por ticket, con resumen de categorías y patrones encontrados.

---
