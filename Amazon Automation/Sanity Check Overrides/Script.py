# %%
import pandas as pd
from datetime import datetime, timedelta
import os

# %%
# Carga del archivo Excel
file_path = "C:/Users/danivo/Desktop/Scripts/TNT Sanity Check/Data_OB.xlsx"  # <- cambia esto por la ruta de tu archivo
closures_df = pd.read_excel(file_path, sheet_name="Closures")
base_path = r"W:\Team Spaces\COS Team\Control Tower\Automated_Reports\OB\TNT Opening Hours Monthly Review\download"
# Extrae lista única de sites desde la columna Origin
#sites = closures_df["Origin"].dropna().unique().tolist()
sites = ['SITE','SITE']
print(sites)

# %%
# Fecha incluida en el nombre del archivo
fecha_archivo = "20250913"

# Diccionario final
site_sheets = {}

for site in sites:
    file_name = f"{site}_TNT_{fecha_archivo}.xlsx"
    file_path = os.path.join(base_path, file_name)

    try:
        df = pd.read_excel(file_path, sheet_name="OUTBOUND", header=None)
        site_sheets[site] = df
    except Exception as e:
        print(f"❌ Error cargando {site}: {e}")

# %%
def extraer_overrides_de_todos_los_sites(site_sheets):
    """
    Recorre el diccionario site_sheets y extrae todos los single-day overrides
    en formato real_df: Origin | Date | Day | Real Open Start | Real Open End
    """
    all_overrides = []

    for site, df_raw in site_sheets.items():
        override_col = df_raw.columns[-2]
        hours_col = df_raw.columns[-1]

        current_date = None

        for _, row in df_raw.iterrows():
            fecha_raw = row[override_col]
            hora_raw = row[hours_col]

            # Capturar la fecha si está presente
            if pd.notna(fecha_raw):
                try:
                    current_date = pd.to_datetime(str(fecha_raw)).date()
                except:
                    continue

            # Si no hay fecha o hora, omitir
            if pd.isna(hora_raw) or pd.isna(current_date):
                continue

            hora_text = str(hora_raw).strip().upper()

            if hora_text == "CLOSED":
                all_overrides.append({
                    "Origin": site,
                    "Date": current_date,
                    "Day": pd.to_datetime(current_date).strftime("%a").upper()[:3],
                    "Real Open Start": "CLOSED",
                    "Real Open End": "CLOSED"
                })
            elif "OPEN 24 HOURS" in hora_text:
                all_overrides.append({
                    "Origin": site,
                    "Date": current_date,
                    "Day": pd.to_datetime(current_date).strftime("%a").upper()[:3],
                    "Real Open Start": "00:00",
                    "Real Open End": "23:58"
                })
            elif "-" in hora_text:
                try:
                    start, end = hora_text.split("-")
                    all_overrides.append({
                        "Origin": site,
                        "Date": current_date,
                        "Day": pd.to_datetime(current_date).strftime("%a").upper()[:3],
                        "Real Open Start": start.strip(),
                        "Real Open End": end.strip()
                    })
                except:
                    continue

    return pd.DataFrame(all_overrides)


# %%
# Asegurarse del formato correcto
closures_df["Closure Start DateTime"] = pd.to_datetime(closures_df["Closure Start Date"].astype(str) + " " + closures_df["Closure Start Time"].astype(str))
closures_df["Closure End DateTime"] = pd.to_datetime(closures_df["Closure End Date"].astype(str) + " " + closures_df["Closure End Time"].astype(str))

# Crear estructura final
open_rows = []

# Procesar por Origin
for origin in closures_df["Origin"].unique():
    origin_df = closures_df[closures_df["Origin"] == origin]

    # Obtener el rango de días afectado
    start_day = origin_df["Closure Start DateTime"].min().normalize()
    end_day = origin_df["Closure End DateTime"].max().normalize()

    current_day = start_day
    while current_day <= end_day:
        day_start = datetime.combine(current_day, datetime.min.time())
        day_end = datetime.combine(current_day, datetime.max.time()).replace(hour=23, minute=59)

        open_intervals = [(day_start, day_end)]

        # Aplicar cierres de ese site y día
        for _, row in origin_df.iterrows():
            close_start = row["Closure Start DateTime"]
            close_end = row["Closure End DateTime"]

            if close_end <= day_start or close_start >= day_end:
                continue  # fuera del día

            new_open_intervals = []
            for open_start, open_end in open_intervals:
                # Lógica de recorte de intervalos
                if close_start <= open_start and close_end >= open_end:
                    continue  # cerrado completamente
                elif close_start <= open_start and close_end < open_end:
                    new_open_intervals.append((close_end, open_end))
                elif close_start > open_start and close_end >= open_end:
                    new_open_intervals.append((open_start, close_start))
                elif close_start > open_start and close_end < open_end:
                    new_open_intervals.append((open_start, close_start))
                    new_open_intervals.append((close_end, open_end))
                else:
                    new_open_intervals.append((open_start, open_end))
            open_intervals = new_open_intervals

        # Guardar resultados para ese día
        for open_start, open_end in open_intervals:
            open_rows.append({
                "Origin": origin,
                "Date": current_day.date(),
                "Open Start Time": open_start.strftime("%H:%M"),
                "Open End Time": open_end.strftime("%H:%M")
            })

        current_day += timedelta(days=1)

# Crear DataFrame final
open_df = pd.DataFrame(open_rows)
print(open_df)


# %%
def extraer_weekly_schedule(xos_df):
    columns = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
    header_row_idx = xos_df.apply(lambda row: row.astype(str).str.contains("SUN", na=False)).any(axis=1)
    header_index = xos_df[header_row_idx].index[0]

    weekly_part = xos_df.iloc[header_index+1:, :7]
    weekly_part.columns = columns
    weekly_part = weekly_part.dropna(how="all")

    weekly_schedule = {}
    for day in columns:
        slots = weekly_part[day].dropna().astype(str).tolist()
        parsed = []

        for s in slots:
            s = s.strip().upper()
            if s == "CLOSED":
                continue
            elif s == "OPEN 24 HOURS":
                parsed.append("00:00-23:59")
            else:
                parsed.append(s)

        weekly_schedule[day] = parsed

    return weekly_schedule


# %%
def time_overlap(start1, end1, start2, end2):
    fmt = "%H:%M"
    s1, e1 = datetime.strptime(start1, fmt), datetime.strptime(end1, fmt)
    s2, e2 = datetime.strptime(start2, fmt), datetime.strptime(end2, fmt)
    return s1 < e2 and s2 < e1

# %%
def generar_horarios_reales_por_site(open_df, site_sheets):
    real_open_rows = []

    for site in open_df["Origin"].unique():
        if site not in site_sheets:
            print(f"⚠️  Hoja '{site}' no encontrada. Se omite.")
            continue

        df = site_sheets[site]
        weekly_schedule = extraer_weekly_schedule(df)
        open_subset = open_df[open_df["Origin"] == site]

        # Obtener el rango de fechas del site basándonos en open_df
        all_dates = pd.date_range(open_subset["Date"].min(), open_subset["Date"].max(), freq='D')
        dates_con_open = pd.to_datetime(open_subset["Date"]).dt.date.unique()
        dates_faltantes = [d.date() for d in all_dates if d.date() not in dates_con_open]

        # 🔁 AÑADIR días faltantes como CLOSED si están afectados por closures (incluso si weekly_schedule está vacío)
        for d in dates_faltantes:
            weekday = pd.to_datetime(d).strftime("%a").upper()[:3]

            # Verificar si el día está cubierto por un cierre en closures_df
            closures_site = closures_df[closures_df["Origin"] == site]
            d_start = datetime.combine(d, datetime.min.time())
            d_end = datetime.combine(d, datetime.max.time())

            esta_en_closure = any(
                (closures_site["Closure Start DateTime"] <= d_end) &
                (closures_site["Closure End DateTime"] >= d_start)
            )

            if esta_en_closure:
                real_open_rows.append({
                    "Origin": site,
                    "Date": d,
                    "Day": weekday,
                    "Real Open Start": "CLOSED",
                    "Real Open End": "CLOSED"
                })

        # Procesar días con apertura parcial o total
        for date, subset in open_subset.groupby("Date"):
            weekday = pd.to_datetime(date).strftime("%a").upper()[:3]
            regular_slots = weekly_schedule.get(weekday, [])
            found_overlap = False

            for _, row in subset.iterrows():
                open_start = row["Open Start Time"]
                open_end = row["Open End Time"]

                for slot in regular_slots:
                    try:
                        slot_start, slot_end = slot.split("-")
                        if time_overlap(slot_start, slot_end, open_start, open_end):
                            real_start = max(slot_start, open_start)
                            real_end = min(slot_end, open_end)
                            real_open_rows.append({
                                "Origin": site,
                                "Date": pd.to_datetime(date).date(),
                                "Day": weekday,
                                "Real Open Start": real_start,
                                "Real Open End": real_end
                            })
                            found_overlap = True
                    except:
                        continue

            # Si no hubo ningún solape y había horario regular, marcar como cerrado
            if not found_overlap and regular_slots:
                real_open_rows.append({
                    "Origin": site,
                    "Date": pd.to_datetime(date).date(),
                    "Day": weekday,
                    "Real Open Start": "CLOSED",
                    "Real Open End": "CLOSED"
                })

    # Crear DataFrame de resultados
    real_df = pd.DataFrame(real_open_rows)

    # FILTRAR: eliminar días cuyo horario real coincide exactamente con el horario regular
    filtrados = []

    for (site, date), group in real_df.groupby(["Origin", "Date"]):
        weekday = pd.to_datetime(date).strftime("%a").upper()[:3]
        site_df = site_sheets.get(site)
        if site_df is None:
            continue
        weekly_schedule = extraer_weekly_schedule(site_df)
        expected_slots = weekly_schedule.get(weekday, [])

        real_slots = [f"{row['Real Open Start']}-{row['Real Open End']}" for _, row in group.iterrows()]

        if sorted(real_slots) != sorted(expected_slots):
            filtrados.append(group)

    if filtrados:
        final_df = pd.concat(filtrados, ignore_index=True)
    else:
        final_df = pd.DataFrame(columns=real_df.columns)
    return final_df

# %%
# Detecta cierres totales de un día completo (de 00:00 a 23:59 en un mismo día) y asegurarse de que esos días se añadan al real_df como "CLOSED".
def añadir_cierres_totales(closures_df, real_df):
    cierres_totales = []

    for _, row in closures_df.iterrows():
        origin = row["Origin"]
        start_dt = pd.to_datetime(f"{row['Closure Start Date']} {row['Closure Start Time']}")
        end_dt = pd.to_datetime(f"{row['Closure End Date']} {row['Closure End Time']}")

        # Mismo día + cierre total de 00:00 a 23:59
        if start_dt.date() == end_dt.date() and start_dt.time() == datetime.strptime("00:00", "%H:%M").time() and end_dt.time() == datetime.strptime("23:59", "%H:%M").time():
            cierre_fecha = start_dt.date()
            cierre_dia = start_dt.strftime("%a").upper()[:3]
            cierres_totales.append({
                "Origin": origin,
                "Date": cierre_fecha,
                "Day": cierre_dia,
                "Real Open Start": "CLOSED",
                "Real Open End": "CLOSED"
            })

    # Convertir a DataFrame y añadir a real_df
    cierres_df = pd.DataFrame(cierres_totales)
    real_df = pd.concat([real_df, cierres_df], ignore_index=True)

    return real_df


# %%
# Convierte los días que están abiertos de forma completa (de 00:00 a 23:59) en "CLOSED".
def marcar_aperturas_completas_como_cerradas(real_df):
    mask = (real_df["Real Open Start"] == "00:00") & (real_df["Real Open End"] == "23:59")
    real_df.loc[mask, "Real Open Start"] = "CLOSED"
    real_df.loc[mask, "Real Open End"] = "CLOSED"
    return real_df

# %%
def añadir_dias_iniciales_cierre_multidia(closures_df, real_df):
    nuevas_filas = []

    for _, row in closures_df.iterrows():
        origin = row["Origin"]
        start_date = pd.to_datetime(row["Closure Start Date"])
        end_date = pd.to_datetime(row["Closure End Date"])
        start_time = pd.to_datetime(str(row["Closure Start Time"])).time()

        # Si empieza a las 00:00 y el cierre pasa al día siguiente
        if start_time == datetime.strptime("00:00", "%H:%M").time() and start_date.date() != end_date.date():
            fecha_cerrada = start_date.date()
            weekday = start_date.strftime("%a").upper()[:3]

            # Solo si no está ya en real_df
            ya_esta = (
                (real_df["Origin"] == origin) &
                (real_df["Date"] == pd.to_datetime(fecha_cerrada))
            ).any()

            if not ya_esta:
                nuevas_filas.append({
                    "Origin": origin,
                    "Date": fecha_cerrada,
                    "Day": weekday,
                    "Real Open Start": "CLOSED",
                    "Real Open End": "CLOSED"
                })

    if nuevas_filas:
        real_df = pd.concat([real_df, pd.DataFrame(nuevas_filas)], ignore_index=True)

    return real_df


# %%
def ordenar_real_df(real_df):
    # Reemplazar "CLOSED" temporalmente por "00:00" para orden correcto
    df_sorted = real_df.copy()
    df_sorted["Sort Time"] = df_sorted["Real Open Start"].replace("CLOSED", "00:00")
    
    df_sorted = df_sorted.sort_values(
        by=["Origin", "Date", "Day", "Sort Time"],
        ascending=[True, True, True, True]
    ).drop(columns="Sort Time").reset_index(drop=True)

    return df_sorted


# %%
# Suponiendo que has leído todos los horarios por separado
real_df = generar_horarios_reales_por_site(open_df, site_sheets)
print(real_df)

# %%
# Suponiendo que has leído todos los horarios por separado
#real_df = generar_horarios_reales_por_site(open_df, site_sheets)
real_df = añadir_cierres_totales(closures_df, real_df)
real_df = marcar_aperturas_completas_como_cerradas(real_df)
real_df = añadir_dias_iniciales_cierre_multidia(closures_df, real_df)
real_df = ordenar_real_df(real_df)
real_df= real_df.drop_duplicates()
#print(real_df)

# %%
overrides_df = extraer_overrides_de_todos_los_sites(site_sheets)
#print(overrides_df)

# %%
def comparar_real_vs_overrides(real_df, overrides_df):
    """
    Compara ambos DataFrames y detecta discrepancias:
    - Filas que están en overrides_df pero no en real_df
    - Filas que están en real_df pero no en overrides_df (aunque esto normalmente no se debería)

    Retorna dos DataFrames:
    - overrides_no_en_real
    - real_no_en_overrides
    """

    # Asegurar mismo tipo y orden de columnas
    cols = ["Origin", "Date", "Day", "Real Open Start", "Real Open End"]
    real_df_comp = real_df[cols].copy().astype(str)
    overrides_df_comp = overrides_df[cols].copy().astype(str)

    # Detectar diferencias
    overrides_no_en_real = overrides_df_comp.merge(
        real_df_comp, how="left", indicator=True, on=cols
    ).query('_merge == "left_only"').drop(columns=["_merge"])

    real_no_en_overrides = real_df_comp.merge(
        overrides_df_comp, how="left", indicator=True, on=cols
    ).query('_merge == "left_only"').drop(columns=["_merge"])

    return overrides_no_en_real, real_no_en_overrides

# %% [markdown]
# ## ----RESULTADOS-----

# %%
closures_df

# %%
from IPython.display import display
"""""
for site, df in site_sheets.items():
    print(f"\n📄 Site: {site}")
    display(df)  # Esto muestra la tabla con formato de Excel
"""""
display(site_sheets["XOS1"])

# %%
display(real_df)

# %%

display(overrides_df)

# %%
overrides_faltan_en_real, real_faltan_en_overrides = comparar_real_vs_overrides(real_df, overrides_df)

print("❌ Overrides que no aparecen en Real_df:")
display(overrides_faltan_en_real)

# %%
print("\n❓ Real_df que no aparecen overrides:")
display(real_faltan_en_overrides)

# %%
from pathlib import Path
from datetime import datetime
import pandas as pd

# Obtener la fecha actual en formato YYYY-MM-DD
fecha_actual = datetime.now().strftime("%Y-%m-%d")

# Ruta de salida con fecha en el nombre
output_path = Path(f"OB_TNT_Horarios_Reporte_{fecha_actual}.xlsx")

# Convertir columnas de fecha a formato YYYY-MM-DD (sin hora)
closures_df["Closure Start Date"] = pd.to_datetime(closures_df["Closure Start Date"]).dt.strftime("%Y-%m-%d")
closures_df["Closure End Date"] = pd.to_datetime(closures_df["Closure End Date"]).dt.strftime("%Y-%m-%d")

# Crear el Excel con múltiples hojas
with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
    real_df.to_excel(writer, sheet_name="Real_Hours", index=False)
    overrides_df.to_excel(writer, sheet_name="Overrides_TNT", index=False)
    overrides_faltan_en_real.to_excel(writer, sheet_name="Overrides_NOT_in_Real", index=False)
    real_faltan_en_overrides.to_excel(writer, sheet_name="Real_NOT_in_Overrides", index=False)
    closures_df.to_excel(writer, sheet_name="Insite_Closures", index=False)

print(f"✅ Reporte generado: {output_path.resolve()}")



