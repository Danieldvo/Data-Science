import os
import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By 
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
import pyinputplus as pyip
from datetime import datetime
import win32com.client as win32

def web_driver(headless: bool = False, log_lv: int = 3, user_data_dir: str = None):
    options = Options()
    options.add_argument(f'log-level={log_lv}')
    options.add_argument("--no-sandbox")

    if user_data_dir:
        usrdir = user_data_dir if user_data_dir != 'auto' else os.path.join(os.getenv('LOCALAPPDATA'), 'Google', 'Chrome', 'User Data')
        options.add_argument(f'user-data-dir={usrdir}')
        options.add_argument('--profile-directory=Default')
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36")

    if headless:
        options.add_argument("--headless=new")
        options.add_argument("window-size=1920,1080")

    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def midway(driver: webdriver, pin: str):
    url = "*****"
    driver.get(url)
    otp = input("Touch Yubikey: ")
    try:
        user_field = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "user_name"))
        )
        user_field.clear()
        user_field.send_keys(os.getlogin())

        password_field = driver.find_element(By.ID, "password")
        password_field.send_keys(pin)
        
        otp_field = driver.find_element(By.ID, "otp")
        otp_field.send_keys(otp)
        
        driver.find_element(By.NAME, "commit").click()
        print("Autenticación completada.")
    except Exception as e:
        print(f"Error durante la autenticación: {e}")
        driver.quit()
        raise

def extract_table_data(driver):
    try:
        # Lista para almacenar los DataFrames con sus títulos
        table_data = []

        # Encontrar todas las tablas con ambas clases
        tables = driver.find_elements(By.CSS_SELECTOR, "table.css-1i81y5r, table.css-nsgqnu")
        
        for table in tables:
            # Buscar el título de la tabla (span anterior más cercano)
            title = table.find_element(By.XPATH, "./preceding::span[@class='css-ljjwvb'][1]").text
            
            # Extraer encabezados
            headers = []
            header_cells = table.find_elements(By.TAG_NAME, "th")
            for cell in header_cells:
                headers.append(cell.text.strip())
            
            # Extraer filas
            all_rows = []
            row_elements = table.find_elements(By.TAG_NAME, "tr")[1:]  # Excluir la fila de encabezados
            
            for row_element in row_elements:
                cells = row_element.find_elements(By.TAG_NAME, "td")
                cell_data = []
                max_lines = 1
                
                # Primero, recolectar todos los datos y determinar el número máximo de líneas
                for cell in cells:
                    p_elements = cell.find_elements(By.TAG_NAME, "p")
                    if p_elements:
                        lines = [p.text.strip() for p in p_elements]
                        cell_data.append(lines)
                        max_lines = max(max_lines, len(lines))
                    else:
                        # Si no hay elementos p, obtener el texto directamente del span
                        span_elements = cell.find_elements(By.TAG_NAME, "span")
                        if span_elements:
                            cell_data.append([span.text.strip() for span in span_elements])
                        else:
                            cell_data.append([cell.text.strip()])
                
                # Crear filas separadas para cada línea de horario
                for line_index in range(max_lines):
                    row = []
                    for cell_lines in cell_data:
                        # Si la celda tiene una línea para este índice, usarla
                        # Si no, usar una celda vacía o la última línea disponible
                        if line_index < len(cell_lines):
                            row.append(cell_lines[line_index])
                        else:
                            row.append('')  # o podrías usar cell_lines[-1] para repetir el último valor
                    all_rows.append(row)
            
            # Crear DataFrame
            df = pd.DataFrame(all_rows, columns=headers)
            table_data.append((title, df))
            print(f"Tabla '{title}' extraída exitosamente")
        
        return table_data

    except Exception as e:
        print(f"Error al extraer las tablas: {e}")
        return []

def save_tables_to_excel(table_data, site_name):
    try:
        # Obtener el directorio del script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        # Definir el directorio de salida
        output_path = os.path.join(script_dir, 'download')

        if not os.path.exists(output_path):
            os.makedirs(output_path)
            print(f"Directorio creado: {output_path}")
        
        current_date = datetime.now().strftime("%Y%m%d")
        output_file = os.path.join(output_path, f"{site_name}_TNT_{current_date}.xlsx")
        
        if os.path.exists(output_file):
            try:
                os.remove(output_file)
                print(f"Archivo existente eliminado: {output_file}")
            except PermissionError:
                print(f"No se pudo eliminar el archivo anterior porque está en uso: {output_file}")
                output_file = os.path.join(output_path, f"{site_name}_TNT_{current_date}_{int(time.time())}.xlsx")
                print(f"Creando archivo con nuevo nombre: {output_file}")

        # Agrupar las tablas por título
        tables_by_title = {}
        for title, df in table_data:
            if title not in tables_by_title:
                tables_by_title[title] = []
            tables_by_title[title].append(df)

        with pd.ExcelWriter(output_file, engine='xlsxwriter') as writer:
            for title, dfs in tables_by_title.items():
                # Limpiar el título para usarlo como nombre de hoja
                sheet_name = ''.join(c for c in title if c.isalnum())[:31]
                
                # Determinar qué DataFrame va primero (css-1i81y5r debe ir a la izquierda)
                if len(dfs) == 2:
                    # Asumimos que el orden en dfs corresponde al orden de las tablas en la página
                    df_combined = pd.concat(dfs, axis=1)
                    df_combined.to_excel(writer, sheet_name=sheet_name, index=False)
                else:
                    # Si solo hay una tabla, la escribimos directamente
                    dfs[0].to_excel(writer, sheet_name=sheet_name, index=False)
                
                # Obtener el objeto workbook y worksheet
                workbook = writer.book
                worksheet = writer.sheets[sheet_name]
                
                # Ajustar el ancho de las columnas
                if len(dfs) == 2:
                    for col_num, column in enumerate(df_combined.columns):
                        max_length = max(
                            df_combined[column].astype(str).apply(len).max(),
                            len(str(column))
                        )
                        worksheet.set_column(col_num, col_num, max_length + 2)
                else:
                    for col_num, column in enumerate(dfs[0].columns):
                        max_length = max(
                            dfs[0][column].astype(str).apply(len).max(),
                            len(str(column))
                        )
                        worksheet.set_column(col_num, col_num, max_length + 2)
                
                print(f"Hoja '{title}' guardada correctamente")
        
        print(f"Datos guardados exitosamente en {output_file}")
        return output_file

    except Exception as e:
        print(f"Error al guardar las tablas: {e}")
        return None

def process_single_site(driver, site_code, max_attempts=2):
    for attempt in range(max_attempts):
        try:
            # Navegar a la página del site
            url = f"https:....../node/{site_code}?tab=HOURS_OF_OPERATION"
            driver.get(url)

            # Esperar a que la página cargue completamente
            time.sleep(5)
            
            # Extraer todas las tablas
            tables_data = extract_table_data(driver)
            
            # Guardar las tablas si se encontraron
            if tables_data:
                output_file = save_tables_to_excel(tables_data, site_code)
                return True
            else:
                print(f"No se encontraron tablas para extraer en {site_code}")
                if attempt < max_attempts - 1:  # Si no es el último intento
                    print(f"Intentando nuevamente ({attempt + 2}/{max_attempts})...")
                    time.sleep(3)  # Esperar un poco antes del siguiente intento
                    continue
                return False
                
        except Exception as e:
            print(f"Error procesando el site {site_code} (Intento {attempt + 1}/{max_attempts}): {e}")
            if attempt < max_attempts - 1:  # Si no es el último intento
                print(f"Intentando nuevamente ({attempt + 2}/{max_attempts})...")
                time.sleep(3)  # Esperar un poco antes del siguiente intento
                continue
            return False
    
    return False

def process_sites(sites):
    # Resultados del procesamiento
    results = {}
    try:
        # Autenticación
        pin = pyip.inputPassword("Enter your PIN > ")
        midway(driver=driver, pin=pin)

        # Procesar cada site
        for site in sites:
            print(f"\nProcesando site: {site}")
            site_start_time = time.time()
            
            success = process_single_site(driver, site)
            
            site_end_time = time.time()
            site_execution_time = site_end_time - site_start_time
            
            results[site] = {
                'success': success,
                'execution_time': site_execution_time
            }
            
            # Pequeña pausa entre sites para evitar problemas
            time.sleep(2)
        
        # Mostrar resumen de resultados
        print("\n=== Resumen de resultados ===")
        for site, result in results.items():
            status = "Éxito" if result['success'] else "Falló"
            print(f"{site}: {status} - Tiempo: {result['execution_time']:.2f} segundos")
            
    except Exception as e:
        print(f"Error durante la ejecución: {e}")

    finally:
        # Cerrar el navegador
        driver.quit()
        
        # Mostrar tiempo de ejecución total
        end_time = time.time()
        total_time = end_time - start_time
        print(f"\nTiempo total de ejecución: {total_time:.2f} segundos")

def read_sites_from_file(filename):
    print(f"Directorio actual: {os.path.dirname(os.path.abspath(__file__))}")
    try:
        # Obtiene la ruta del directorio donde está el script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        # Construye la ruta completa al archivo
        file_path = os.path.join(script_dir, filename)

        print(f"Buscando archivo en: {file_path}")  # Para debug
        
        with open(file_path, 'r') as file:
            sites = [line.strip().rstrip(',') for line in file if line.strip()]
        return sites
    except FileNotFoundError:
        print(f"Error: El archivo {file_path} no fue encontrado.")
        return []
    except Exception as e:
        print(f"Error al leer el archivo: {e}")
        return []

def send_tnt_email():
    try:
        # 1. Obtener el directorio del script y las rutas necesarias
        script_dir = os.path.dirname(os.path.abspath(__file__))
        download_dir = os.path.join(script_dir, 'download')
        email_list_path = r"W:....OB_mailing_list.xlsx"
        template_path = r"W:...\ct_ob_email.html"
       # Leer los sites del archivo sites.txt
        sites_to_process = read_sites_from_file('sites.txt')
        if not sites_to_process:
            print("No se encontraron sites en sites.txt")
            return

        # 2. Verificar que existan los archivos necesarios
        if not os.path.exists(email_list_path):
            print("Error: No se encuentra el archivo OB_mailing_list.xlsx")
            return
        
        if not os.path.exists(template_path):
            print("Error: No se encuentra la plantilla ct_ob_email.html")
            return

        # 3. Leer la plantilla HTML
        try:
            with open(template_path, 'r', encoding='utf-8') as file:
                template_html = file.read()
        except Exception as e:
            print(f"Error al leer la plantilla HTML: {e}")
            return

        # 4. Leer la lista de correos

        try:
            email_df = pd.read_excel(email_list_path, sheet_name="TNT")
            if not all(col in email_df.columns for col in ['Site', 'To']):
                print("Error: El archivo OB_mailing_list.xlsx debe contener las columnas 'Site' y 'To'")
                return
            # Filtrar el DataFrame para incluir solo los sites en sites.txt
            email_df = email_df[email_df['Site'].isin(sites_to_process)]
        except Exception as e:
            print(f"Error al leer OB_mailing_list.xlsx: {e}")
            return


        # 5. Obtener la fecha actual
        current_date = datetime.now().strftime("%Y%m%d")

        # 6. Procesar cada site
        outlook = win32.Dispatch('outlook.application')
        emails_prepared = 0

        for index, row in email_df.iterrows():
            site = row['Site']
            recipients = row['To']
            
            # Buscar el archivo correspondiente al site
            site_file = os.path.join(download_dir, f"{site}_TNT_{current_date}.xlsx")
            
            if not os.path.exists(site_file):
                print(f"No se encontró el archivo para el site {site}")
                continue

            # Crear nuevo correo
            mail = outlook.CreateItem(0)

            # Configurar el correo
            mail.Subject = f"TNT Report - {site} - {current_date}"
            
            # Personalizar el contenido del template
            email_body = (
                "As part of our monthly TNT Opening Hours review process, please find attached the current opening hours configuration for your site. "
  
                "2. <u>Inbound Configuration:</u><br>"
                .....
                ....
                ....

    
                "3. <u>Yard Configuration:</u><br>"
                ....
                ...
                ...


                "<strong>If changes are required:</strong><br>"
               ......
               .....
               ....

    
                "Best regards,<br>"
            )

            # Reemplazar las variables en el template
            html_content = template_html.replace('{report_name}', f'TNT Report - {site}')
            html_content = html_content.replace('{site}', site)
            html_content = html_content.replace('{body}', email_body)
            
            mail.HTMLBody = html_content
            mail.To = recipients
            
            # Adjuntar archivo
            mail.Attachments.Add(site_file)

            # Usar la cuenta correcta de Outlook
            From = None
            for myEmailAddress in outlook.Session.Accounts:
                if "****@amazon.com" in str(myEmailAddress):
                    From = myEmailAddress
                    break

            if From is not None:
                mail._oleobj_.Invoke(*(64209, 0, 8, 0, From))

            # Mostrar el correo para revisión
            mail.Display()
            emails_prepared += 1
            print(f"Correo preparado para {site} - Destinatarios: {recipients}")

        print(f"\nTotal de correos preparados: {emails_prepared}")

    except Exception as e:
        print(f"Error al preparar los correos: {e}")

if __name__ == "__main__":

    # Iniciar el navegador
    headless_mode = False  
    driver = web_driver(headless_mode, user_data_dir='auto')
    start_time = time.time()

    # Leer sites desde el archivo
    sites = read_sites_from_file('sites.txt')

    if sites:
        process_sites(sites)
    else:
        print("No se pudieron cargar los sites. El programa se cerrará.")
        driver.quit()

    send_tnt_email()
