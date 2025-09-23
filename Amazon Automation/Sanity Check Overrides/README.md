## 📖 How the Script Works

The script performs a **sanity check of TNT site opening hours**, comparing multiple data sources and generating an Excel report with discrepancies.  

---

### 🔎 Workflow

1. **Load Closures (Closures sheet)**
   - Reads `Data_OB.xlsx`, sheet `Closures`.  
   - Contains for each `Origin` (site) the closure intervals (`Closure Start Date/Time` – `Closure End Date/Time`).  
   - Converts them into proper `datetime` objects.  

2. **Load TNT files for each site**
   - Looks for Excel files in the `download` folder with the format `<SITE>_TNT_<date>.xlsx`.  
   - Each file contains:  
     - **Weekly schedule** (SUN–SAT).  
     - **Single-day overrides** (e.g., `CLOSED`, `OPEN 24 HOURS`, `08:00-14:00`).  

3. **Reconstruct Real Opening Hours (`real_df`)**
   - Starts from a full-day open interval (00:00–23:59).  
   - Subtracts closures from `Closures`.  
   - Cross-checks with weekly schedule slots.  
   - Produces the “real” open hours per day per site.  

4. **Additional Adjustments**
   - Adds days with total closures (`00:00–23:59`).  
   - Converts full-day openings into `CLOSED` (for consistency).  
   - Adds the first days of multi-day closures.  
   - Sorts results and removes duplicates.  

5. **Extract Overrides (`overrides_df`)**
   - From each TNT file, parses overrides column:  
     - `CLOSED` → fully closed day.  
     - `OPEN 24 HOURS` → 00:00–23:58.  
     - `HH:MM-HH:MM` → custom open interval.  

6. **Compare Real vs Overrides**
   - Function `comparar_real_vs_overrides()` detects:  
     - **Overrides missing in Real** → planned override not reflected in reconstructed schedule.  
     - **Real missing in Overrides** → opening hours not documented in TNT overrides.  

7. **Generate Final Report**
   - Creates an Excel file `OB_TNT_Horarios_Reporte_<date>.xlsx` with 5 sheets:  
     - `Real_Hours` – reconstructed daily hours.  
     - `Overrides_TNT` – all extracted overrides.  
     - `Overrides_NOT_in_Real` – overrides missing in real_df.  
     - `Real_NOT_in_Overrides` – real hours missing in overrides.  
     - `Insite_Closures` – original closure data.  

---

### 🎯 Summary

The script:
- **Reads** closures and TNT schedules.  
- **Reconstructs** the real daily open hours per site.  
- **Compares** them with single-day overrides.  
- **Detects discrepancies** between planned vs actual schedules.  
- **Generates a consolidated Excel report** for analysis by the operations team.  
