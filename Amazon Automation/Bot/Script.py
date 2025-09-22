import os
import requests
import schedule
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from retrying import retry
import boto3
from decimal import Decimal
import boto3
from datetime import datetime
import json
import threading

#Variable global
df_rodeo_accumulated = pd.DataFrame()

class AWSLogger:
    def __init__(self):
        self.client = boto3.client('logs')  # o la región que uses
        self.log_group = '/sdc-reactive-transfers-bot'
        self.log_stream = f"{datetime.now().strftime('%Y-%m-%d')}-{os.getlogin()}"
        self.sequence_token = None
        self._initialize_logging()

    def _initialize_logging(self):
        """Inicializa el log stream si no existe"""
        try:
            # Intentar crear el log stream
            try:
                self.client.create_log_stream(
                    logGroupName=self.log_group,
                    logStreamName=self.log_stream
                )
                print(f"Log stream {self.log_stream} created successfully")
            except self.client.exceptions.ResourceAlreadyExistsException:
                print(f"Using existing log stream {self.log_stream}")

        except Exception as e:
            print(f"Error initializing CloudWatch Logs: {e}")

    def log(self, message, log_type="INFO", details=None):
        """Envía un log a CloudWatch"""
        try:
            timestamp = int(datetime.now().timestamp() * 1000)
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'type': log_type,
                'message': message,
                'details': details or {}
            }

            params = {
                'logGroupName': self.log_group,
                'logStreamName': self.log_stream,
                'logEvents': [{
                    'timestamp': timestamp,
                    'message': json.dumps(log_entry)
                }]
            }

            if self.sequence_token:
                params['sequenceToken'] = self.sequence_token

            response = self.client.put_log_events(**params)
            self.sequence_token = response['nextSequenceToken']

        except Exception as e:
            print(f"Error sending log to CloudWatch: {e}")

# Crear instancia global del logger
aws_logger = AWSLogger()

def update_bot(script, status, user):
    print(f"Uploading {script} bot execution to tracker...")
    
    dynamodb = boto3.resource('dynamodb', region_name='eu-central-1')
    table = dynamodb.Table('ct-ob-bots')
    timestamp = Decimal(str(datetime.now().timestamp()))

    try:
        item = {
            'bot': script,
            'status': status,
            'time': timestamp,
            'user': user,
            'chang': Decimal('1')
        }

        table.put_item(Item=item)
        print("Uploaded to tracker")

    except Exception as e:
        print(f"An error occurred: {str(e)}")

# Sites and webhooks configuration
SITES_CONFIG = {
    "sites": ["",""..],
    "sitesS3": ["",""...],
    "base_url": "https://xxx",
    "webhooks": {
        "SITE": "..",
        "SITE": ".."
    }
}

# Status webhook for monitoring
STATUS_WEBHOOK = "https://hooks.chime.aws/incomingwebhooks/bd0844e5-eb6b-4c53-9495-5465167c390b?token=aTdlWkhJNHZ8MXxVOXB2T3drWElSNjNJTzJUQ00yNi05aUJiWjRvOHduM3JfT0h0alJmc21R"

# Counter for consecutive failures
CONSECUTIVE_FAILURES = 0

def is_timeout_error(error):
    """Determina si es un error de timeout"""
    timeout_errors = [
        "timeout",
        "Timed out receiving message from renderer",
        "ERR_TIMED_OUT",
        "net::ERR_TIMED_OUT",
    ]
    
    error_str = str(error).lower()
    return any(err.lower() in error_str for err in timeout_errors)

def send_status_message(message, is_error=False):
    """Sends status messages to the main webhook"""
    try:
        if is_error:
            message = f"🚨 ERROR SDC Reactive Transfers Bot: {message} - Bot needs restart!. \n Script located in: W:/Team Spaces/COS Team/Control Tower/Automated_Reports/OB/SDC_Reactive_transfers_bot"
        else:
            message = f"ℹ️ STATUS SDC Reactive Transfers Bot: {message}"
            
        response = requests.post(STATUS_WEBHOOK, json={"Content": message}, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Error sending status message: {e}")
        return False

def validate_webhooks():
    """Validates that all sites have corresponding webhooks"""
    missing_webhooks = [site for site in SITES_CONFIG["sites"] if site not in SITES_CONFIG["webhooks"]]
    if missing_webhooks:
        print(f"Missing webhooks for sites: {', '.join(missing_webhooks)}")
        raise ValueError(f"Missing webhooks for sites: {', '.join(missing_webhooks)}")
    return True

def get_driver():
    """Creates and configures a new Chrome driver"""
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-logging")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-default-apps")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-web-security")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-translate")
    options.add_argument("--disable-features=TranslateUI")
    options.page_load_strategy = 'eager'
    
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)
@retry(stop_max_attempt_number=3, wait_fixed=2000)
def get_table_data(site, return_df=False):
    driver = None
    try:
        driver = get_driver()
        url = f"{SITES_CONFIG['base_url']}/{site}/ItemListCSV?_enabledColumns=on&enabledColumns=IS_REACTIVE_TRANSFER&Excel=true&IsReactiveTransfer=YES&shipmentType=TRANSSHIPMENTS"

        driver.get(url)

        if "login" in driver.current_url.lower():
            print(f"Authentication error in {site}. Please verify VPN connection.")
            return pd.DataFrame() if return_df else None

        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Accessing {site}")

        wait = WebDriverWait(driver, 20)
        table = wait.until(EC.presence_of_element_located((By.XPATH, "//table")))

        rows = driver.execute_script("""
            const rows = document.getElementsByTagName('tr');
            const data = [];
            for (let i = 0; i < rows.length; i++) {
                const cells = rows[i].getElementsByTagName(i === 0 ? 'th' : 'td');
                const rowData = [];
                for (let j = 0; j < cells.length; j++) {
                    rowData.push(cells[j].textContent);
                }
                data.push(rowData);
            }
            return data;
        """)

        if not rows:
            print(f"No rows found for {site}")
            return pd.DataFrame() if return_df else None

        headers = rows[0]
        data = rows[1:]

        if not data:
            print(f"No reactive transfers found for {site}")
            message = f"/md ## Reactive Transfers\nNo reactive transfers pending at the moment for {site}"
            success = send_to_chime(message, site)
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Message for {site}: {'Sent \u2713' if success else 'Failed \u2717'}")
            return pd.DataFrame() if return_df else True

        df = pd.DataFrame(data, columns=headers)
        return df if return_df else process_data_and_send_to_chime(df, site)

    except Exception as e:
        print(f"Error processing {site}: {e}")
        return pd.DataFrame() if return_df else None
    finally:
        if driver:
            try:
                driver.quit()
            except Exception as e:
                print(f"Error closing driver for {site}: {e}")

def format_as_markdown_table(df):
    """Formats DataFrame as Markdown table"""
    headers = "| Process Path | Destination Warehouse | Need To Ship By Date | Work Pool | Total Quantity |"
    separator = "|--------------|--------------------|-------------------|-----------|----------------|"
    rows = [
        f"| {row['Process Path']} | {row['Destination Warehouse']} | {row['Need To Ship By Date']} | {row['Work Pool']} | {row['Quantity']:,} |"
        for _, row in df.iterrows()
    ]
    return "\n".join([headers, separator] + rows)

def send_to_chime(message, site):
    """Sends a message to Chime using site-specific webhook"""
    webhook_url = SITES_CONFIG["webhooks"].get(site)
    if not webhook_url:
        print(f"No webhook found for site {site}")
        return False
    
    try:
        response = requests.post(webhook_url, json={"Content": message}, timeout=10)
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        print(f"Chime API error for {site}: {str(e)}")
        return False

def process_data_and_send_to_chime(df, site):
    """Processes data and sends it to Chime"""
    try:
        df['Quantity'] = pd.to_numeric(df['Quantity'], errors='coerce').fillna(0)
        df['Process Path'] = df['Process Path'].fillna('No Process Path')
        
        grouped_df = (df.groupby(['Process Path', 'Destination Warehouse', 
                                 'Need To Ship By Date', 'Work Pool'])
                     ['Quantity'].sum()
                     .reset_index())
        
        grouped_df['Quantity'] = grouped_df['Quantity'].astype(int)
        
        message = f"/md ## Reactive Transfers\n" + format_as_markdown_table(grouped_df)
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        success = send_to_chime(message, site)
        print(f"{timestamp} - Message for {site}: {'Sent ✓' if success else 'Failed ✗'}")
        
        return success
        
    except Exception as e:
        print(f"Error processing data for {site}: {e}")
        return False


def job():
    """Execute main job"""
    global CONSECUTIVE_FAILURES
    job_start_time = datetime.now()
    
    aws_logger.log("Starting job execution", "INFO", {
        "start_time": job_start_time.isoformat()
    })

    try:
        with ThreadPoolExecutor(max_workers=len(SITES_CONFIG["sites"])) as executor:
            futures = []
            for site in SITES_CONFIG["sites"]:
                time.sleep(1)
                futures.append(executor.submit(get_table_data, site))
            
            results = [f.result() for f in futures]
        
        success_count = sum(1 for r in results if r)
        
        aws_logger.log(
            f"Job execution completed",
            "INFO",
            {
                "sites_processed": f"{success_count}/{len(SITES_CONFIG['sites'])}",
                "execution_time": str(datetime.now() - job_start_time)
            }
        )
        print(f"Job completed: {success_count}/{len(SITES_CONFIG['sites'])} sites processed successfully")
        if success_count < len(SITES_CONFIG["sites"]):
            CONSECUTIVE_FAILURES += 1
            aws_logger.log(
                f"Not all sites processed successfully",
                "WARNING",
                {
                    "consecutive_failures": CONSECUTIVE_FAILURES,
                    "sites_processed": success_count,
                    "total_sites": len(SITES_CONFIG["sites"])
                }
            )
            
            if CONSECUTIVE_FAILURES >= 4:
                aws_logger.log(
                    "Critical failure: Too many consecutive failures",
                    "ERROR",
                    {
                        "consecutive_failures": CONSECUTIVE_FAILURES,
                        "last_success_count": success_count
                    }
                )
                send_status_message(
                    f"Failed to process all sites for 4 consecutive runs. Last run: {success_count}/{len(SITES_CONFIG['sites'])} sites processed",
                    is_error=True
                )
                #os._exit(1)
        else:
            CONSECUTIVE_FAILURES = 0

    except Exception as e:
        aws_logger.log(
            f"Error in job execution: {str(e)}",
            "ERROR",
            {
                "error_type": type(e).__name__,
                "error_details": str(e)
            }
        )
        print(f"Error in job execution: {e}")

def upload_to_s3():
    from io import StringIO

    print("Starting S3 upload process using Selenium...")

    try:
        now = datetime.now()
        now_plus_48 = now + timedelta(hours=48)
        from_timestamp = int(now.timestamp() * 1000)
        to_timestamp = int(now_plus_48.timestamp() * 1000)

        sites = SITES_CONFIG["sitesS3"]
        all_rodeo_data = []

        for site in sites:
            success = False
            for attempt in range(3):  # Máximo 3 intentos
                driver = None
                try:
                    rodeo_url = (
                        f"https://rodeo.amazon.com/{site}/ItemListCSV?Excel=true"
                        f"&ExSDRange.RangeStartMillis={from_timestamp}"
                        f"&ExSDRange.RangeEndMillis={to_timestamp}"
                        f"&shipmentType=TRANSSHIPMENTS"
                    )

                    driver = get_driver()
                    driver.get(rodeo_url)

                    # Verificamos si estamos logueados
                    if "login" in driver.current_url.lower():
                        print(f"❌ Not authenticated for site {site} - check VPN or SSO session.")
                        time.sleep(5)
                        continue

                    # Esperar a que la tabla esté disponible
                    wait = WebDriverWait(driver, 20)
                    table = wait.until(EC.presence_of_element_located((By.XPATH, "//table")))

                    # Extraer HTML y convertir a DataFrame
                    html = driver.page_source
                    tables = pd.read_html(StringIO(html))
                    site_data = tables[0]
                    site_data["orig_site"] = site
                    site_data = site_data[site_data['Work Pool'] != 'PendingInventoryBinding']

                    all_rodeo_data.append(site_data)
                    print(f"✅ Data downloaded from {site}")
                    success = True
                    break

                except Exception as e:
                    print(f"❌ Attempt {attempt + 1}: Error downloading from {site}: {e}")
                    time.sleep(5)
                finally:
                    if driver:
                        try:
                            driver.quit()
                        except:
                            pass

            if not success:
                print(f"❌ All attempts failed for {site}")

        if not all_rodeo_data:
            print("No data collected for S3 upload.")
            return

        rodeo = pd.concat(all_rodeo_data, ignore_index=True)
        csv_buffer = rodeo.to_csv(index=False).encode('utf-8')

        s3 = boto3.client('s3')
        s3.put_object(
            Bucket='ct-ob-reporting',
            Key='tso_transcaps/rodeo/rodeo.csv',
            Body=csv_buffer
        )

        print("✅ Upload to S3 completed")
        aws_logger.log("Upload to S3 completed", "INFO", {"rows_uploaded": len(rodeo)})

    except Exception as e:
        print(f"❌ Error during S3 upload: {e}")
        aws_logger.log("Upload to S3 failed", "ERROR", {"error": str(e)})



if __name__ == "__main__":
    print("Starting initial job...")
    username = os.getlogin()
    
    # Log de inicialización en CloudWatch
    aws_logger.log("Bot initialization", "INFO", {
        "user": username,
        "start_time": datetime.now().isoformat()
    })
    
    # Mensaje a Chime
    send_status_message(f"Bot started and running by {username}")
    
    try:
        # 1) Primer latido inmediato
        update_bot("SDC", "started", username)
        
        # Validación de webhooks
        if not validate_webhooks():
            aws_logger.log("Webhook validation failed", "ERROR")
            raise ValueError("Webhook validation failed")
        
        # 2) Segundo latido exacto a los 15 minutos
        def delayed_alive():
            update_bot("SDC", "started", username)
            send_status_message("Bot heartbeat sent after 15 minutes")
            print("Second heartbeat (alive) sent to tracker")
        
        timer = threading.Timer(15 * 60, delayed_alive)  # 15 minutos = 900 segundos
        timer.start()
        
        # --- Programación de jobs normales ---
        for hour in range(24):
            for minute in [0, 15, 30, 45]:
                schedule_time = f"{hour:02d}:{minute:02d}"
                schedule.every().day.at(schedule_time).do(job)

        # Programación de subidas a S3
        schedule.every().day.at("06:00").do(upload_to_s3)
        schedule.every().day.at("07:00").do(upload_to_s3)
        schedule.every().day.at("08:00").do(upload_to_s3)
        schedule.every().day.at("12:00").do(upload_to_s3)
        schedule.every().day.at("17:00").do(upload_to_s3)
        schedule.every().day.at("18:00").do(upload_to_s3)

        # Bucle principal
        while True:
            schedule.run_pending()
            time.sleep(1)
            
    except KeyboardInterrupt:
        aws_logger.log("Bot stopped manually", "INFO", {"user": username})
        update_bot("SDC", "stopped", username)
        send_status_message("Bot stopped manually", is_error=True)
        print("\nProgram interrupted by user")
    except Exception as e:
        aws_logger.log("Unexpected error", "ERROR", {
            "error_type": type(e).__name__,
            "error_details": str(e)
        })
        update_bot("SDC", "error", username)
        print(f"\nUnexpected error: {e}")
    finally:
        print("\nProgram finished")
