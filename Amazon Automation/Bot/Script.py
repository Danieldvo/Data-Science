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
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from retrying import retry

# Sites and webhooks configuration
SITES_CONFIG = {
    "sites": ["****", "****", "****", "****"],
    "base_url": "https://****.amazon.com",
    "webhooks": {
        "****": "https://hooks.chime.aws/incomingwebhooks...........",
        "****": "https://hooks.chime.aws/incomingwebhooks...........",
        "****": "https://hooks.chime.aws/incomingwebhooks...........",
        "****": "https://hooks.chime.aws/incomingwebhooks..........."
    }
}

# Status webhook for monitoring
STATUS_WEBHOOK = "https://hooks.chime.aws/incomingwebhooks/......R"

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
def get_table_data(site):
    """Gets table data for a specific site"""
    driver = None
    try:
        driver = get_driver()
        url = f"{SITES_CONFIG['base_url']}/{site}/ItemListCSV?_enabledColumns=on&enabledColumns=IS_REACTIVE_TRANSFER&Excel=true&IsReactiveTransfer=YES&shipmentType=TRANSSHIPMENTS"
        
        driver.get(url)
        
        # Authentication verification
        if "login" in driver.current_url.lower():
            print(f"Authentication error in {site}. Please verify VPN connection.")
            return None
            
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
            return None
            
        headers = rows[0]
        data = rows[1:]
        
        if not data:
            print(f"No data found for {site}")
            return None
            
        df = pd.DataFrame(data, columns=headers)
        return process_data_and_send_to_chime(df, site)
        
    except Exception as e:
        print(f"Error processing {site}: {e}")
        return None
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
    print(f"\n{job_start_time.strftime('%Y-%m-%d %H:%M:%S')} - Starting job")
    
    try:
        with ThreadPoolExecutor(max_workers=len(SITES_CONFIG["sites"])) as executor:
            futures = []
            for i, site in enumerate(SITES_CONFIG["sites"]):
                time.sleep(1)
                futures.append(executor.submit(get_table_data, site))
            
            results = [f.result() for f in futures]
        
        success_count = sum(1 for r in results if r)
        
        # Verificar si todos los sites fueron procesados
        if success_count < len(SITES_CONFIG["sites"]):
            CONSECUTIVE_FAILURES += 1
            if CONSECUTIVE_FAILURES >= 4:
                send_status_message(
                    f"Failed to process all sites for 4 consecutive runs. Last run: {success_count}/{len(SITES_CONFIG['sites'])} sites processed",
                    is_error=True
                )
                print("Demasiados fallos consecutivos. Terminando el programa.")
                os._exit(1)  # Forzar la terminación del programa
        else:
            CONSECUTIVE_FAILURES = 0  # Reiniciar contador si todo fue exitoso
            
        # Send periodic status update
        if job_start_time.hour % 6 == 0 and job_start_time.minute < 15:
            send_status_message(f"Bot running normally. Sites processed: {success_count}/{len(SITES_CONFIG['sites'])}")
            
        print(f"Job completed: {success_count}/{len(SITES_CONFIG['sites'])} sites processed successfully")
    except Exception as e:
        print(f"Error in job execution: {e}")

if __name__ == "__main__":
    print("Starting initial job...")
    send_status_message("Bot started and running")
    
    try:
        # Validate webhooks before starting
        if not validate_webhooks():
            raise ValueError("Webhook validation failed")
            
        # Execute initial job
        job()
        
        # Schedule job every 15 minutes
        schedule.every(15).minutes.do(job)

        # Main loop
        while True:
            schedule.run_pending()
            time.sleep(1)
            
    except KeyboardInterrupt:
        send_status_message("Bot stopped manually", is_error=True)
        print("\nProgram interrupted by user")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
    finally:
        print("\nProgram finished")
