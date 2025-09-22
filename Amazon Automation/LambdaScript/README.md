# AWS Lambda – Stuck Shipments Reporting

Este módulo implementa una función **AWS Lambda** para la gestión y notificación de envíos atascados (*Stuck Shipments*) en sites de Amazon.  
El proceso automatiza la lectura de datos desde S3, genera reportes en Excel por `warehouse_id` y envía notificaciones personalizadas por correo electrónico usando **Amazon SES**.

---

## 🚀 Flujo de trabajo

1. **Carga de datos**
   - Descarga un CSV de `etl-jobs-ct/stuckshipment/ETL/`.
   - Carga una plantilla Excel desde `etl-jobs-ct/stuckshipment/template.xlsx`.

2. **Procesamiento**
   - Filtra el dataset por cada `warehouse_id`.
   - Completa la plantilla Excel con los datos correspondientes.
   - Guarda cada archivo generado en `etl-jobs-ct/stuckshipment/output/`.

3. **Notificación**
   - Prepara un correo HTML con **SES**.
   - Adjunta el Excel generado por site.
   - Inserta un logo inline (extraído como Base64 desde `ct-ob-reporting/assets/logo_base64.txt`).
   - Personaliza el cuerpo usando una plantilla HTML desde S3 (`ct-ob-reporting/assets/xxxx.html`).

4. **Limpieza**
   - Elimina los archivos generados en la carpeta `output`.
   - Actualiza el tracker en DynamoDB (`ct-ob-reports`).

---

## 📂 Estructura del proyecto

- `mi_lambda.py` → Script principal con la función `lambda_handler`.
- `README.md` → Documentación de esta Lambda.
- **S3 buckets involucrados**:
  - `etl-jobs-ct` → CSV de entrada, plantilla y reportes generados.
  - `ct-ob-reporting` → Assets (HTML, logo base64).
- **DynamoDB**
  - Tabla: `ct-ob-reports` (tracking de ejecuciones).
- **SES**
  - Envío de correos con reportes por site.

---

## ⚙️ Configuración necesaria

- **Permisos IAM**:  
  La Lambda requiere acceso a:
  - `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject` sobre `etl-jobs-ct` y `ct-ob-reporting`.
  - `ses:SendRawEmail`.
  - `dynamodb:PutItem` sobre la tabla `ct-ob-reports`.

- **Variables de entorno**:
  - `REGION_NAME` = `eu-central-1`
  - `SOURCE_EMAIL` = Dirección configurada en SES para envío.

- **Mappings de correo (`email_mapping`)**:  
  Diccionario que asigna cada `warehouse_id` a una lista de destinatarios.  
  ```python
  email_mapping = {
      'SITE1': 'correo1@ejemplo.com;correo2@ejemplo.com',
      'SITE2': 'otro@ejemplo.com'
  }
