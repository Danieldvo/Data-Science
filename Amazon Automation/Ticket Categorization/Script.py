import re
import os
import pandas as pd
from collections import defaultdict

# ==== CONFIGURACIÓN DE RUTAS ====
INPUT_FOLDER = 'input'
OUTPUT_FOLDER = 'output'

COMMENTS_FILE = os.path.join(INPUT_FOLDER, 'sim_comments.txt')
TICKETS_LIST_FILE = os.path.join(INPUT_FOLDER, 'tickets_to_find.txt')

# ==== ESTRUCTURAS ====
categorized_tickets = defaultdict(dict)
ticket_categories = defaultdict(list)
all_ticket_ids = set()

# ==== DEFINICIÓN DE PATRONES ====
patterns = {
    'Max_Capacity_Express_Services': [
        r'(?i)ups_express_saver_eu_row',
        r'(?i)shipmethod:\s*ups_express',
        r'(?i)mondial_relay_std_store',
        r'(?i)shipmethod:\s*mondial_relay',
        r'(?i)max\s+pickup\s+capacity\s+has\s+been\s+reached',
        r'(?i)maximum\s+capacity\s+for\s+given\s+ship-option',
        r'(?i)capMeasurementType:\s*pkg_count',
        r'(?i)capMeasurementType:\s*cubic_volume',
        r'(?i)(?:fc|warehouse(?:\s+id)?):(?:\s*)(xfro|xfrs|xitk)',
        r'(?i)cancel(?:led)?\s+(?:for|to)\s+(?:system\s+to\s+)?re-assign',
        r'(?i)shipment\s+(?:must\s+be\s+)?cancelled'
    ],
    'Delivery_Area_Restrictions': [
        r'(?i)rapid_flood_03',
        r'(?i)christmas_markets_[a-z_]+',
        r'(?i)fr_mrela_38_quality',
        r'(?i)max\s+destination\s+capacity\s+has\s+been\s+reached\s+for\s+carrier\s+delivery\s+area',
        r'(?i)carrier\s+delivery\s+area:\s*([^\n]+)',
        r'(?i)(?:fc|warehouse(?:\s+id)?):(?:\s*)(xfrs|xfro|dqv6)',
        r'(?i)re-slam\s+after\s+cpt',
        r'(?i)late\s+slam',
        r'(?i)cancel(?:led)?\s+(?:for|to)\s+re-assign'
    ],
    'Capacity_Details': [
        r'(?i)capacity(?:\s+has\s+been)?\s+reached\s+for\s+fc:([^\s]+)',
        r'(?i)shipMethod:([^\s]+)',
        r'(?i)capMeasurementType:([^\s]+)',
        r'(?i)processingCapabilityName:([^\s]+)',
        r'(?i)warehouseCycleName:([^\s]+)',
        r'(?i)destinationWarehouseId:([^\s]+)',
        r'(?i)sortCode:([^\s]+)'
    ]
}

# ==== FUNCIONES ====

def read_tickets_to_find(path):
    try:
        with open(path, 'r', encoding='utf-8') as file:
            return set(line.strip() for line in file if line.strip())
    except Exception as e:
        print(f"Error leyendo el archivo de tickets: {e}")
        return set()

def find_matching_patterns(text, pattern_list):
    matches = set()
    for pattern in pattern_list:
        for match in re.finditer(pattern, text.lower()):
            matches.add(match.group())
    return list(matches)

def categorize_ticket(text, ticket_id):
    all_ticket_ids.add(ticket_id)
    matched = False
    for category, pattern_list in patterns.items():
        matches = find_matching_patterns(text, pattern_list)
        if matches:
            categorized_tickets[category][ticket_id] = matches
            ticket_categories[ticket_id].append(category)
            matched = True
    if not matched:
        categorized_tickets['Unclassified'][ticket_id] = []
        ticket_categories[ticket_id].append('Unclassified')

def process_tickets(document_text, tickets_to_find):
    split_tickets = re.split(r'=== TICKET: ([\w\-]+) ===', document_text)
    for i in range(1, len(split_tickets), 2):
        ticket_id = split_tickets[i]
        if ticket_id in tickets_to_find:
            content = split_tickets[i + 1]
            categorize_ticket(content, ticket_id)

def export_results():
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    # Exportar vista por categoría
    rows = []
    for category, tickets in categorized_tickets.items():
        for ticket_id, matches in tickets.items():
            rows.append({
                'Category': category,
                'Ticket_ID': ticket_id,
                'Matching_Patterns': '; '.join(sorted(set(matches))) or 'No patterns matched',
                'Total_Categories': len(ticket_categories[ticket_id]),
                'All_Categories': '; '.join(sorted(ticket_categories[ticket_id]))
            })

    df_cat = pd.DataFrame(rows)
    df_cat.to_csv(os.path.join(OUTPUT_FOLDER, 'tickets_by_category.csv'), index=False)

    # Exportar vista por ticket
    ticket_rows = []
    for ticket_id in all_ticket_ids:
        categories = ticket_categories[ticket_id]
        all_matches = []
        for category in categories:
            all_matches += categorized_tickets.get(category, {}).get(ticket_id, [])
        ticket_rows.append({
            'Ticket_ID': ticket_id,
            'Number_of_Categories': len(categories),
            'Categories': '; '.join(sorted(categories)),
            'All_Patterns': '; '.join(sorted(set(all_matches))) or 'No patterns matched'
        })

    df_tickets = pd.DataFrame(ticket_rows)
    df_tickets.to_csv(os.path.join(OUTPUT_FOLDER, 'tickets_summary.csv'), index=False)

def print_statistics():
    total = len(all_ticket_ids)
    unclassified = len(categorized_tickets['Unclassified'])
    classified = total - unclassified

    print("\n📊 Estadísticas:")
    print(f"Total de tickets: {total}")
    print(f"Tickets clasificados: {classified} ({classified/total:.2%})")
    print(f"Tickets no clasificados: {unclassified} ({unclassified/total:.2%})")

    print("\n🎯 Tickets por categoría:")
    for category in patterns:
        print(f"{category}: {len(categorized_tickets[category])}")
    print(f"Unclassified: {unclassified}")

    distribution = defaultdict(int)
    for cats in ticket_categories.values():
        distribution[len(cats)] += 1
    print("\n🔄 Distribución por número de categorías:")
    for k, v in sorted(distribution.items()):
        print(f"{v} tickets tienen {k} categoría(s)")

def main():
    tickets_to_find = read_tickets_to_find(TICKETS_LIST_FILE)
    if not tickets_to_find:
        print("❌ No se encontraron tickets válidos.")
        return

    try:
        with open(COMMENTS_FILE, 'r', encoding='utf-8') as f:
            document_text = f.read()
    except Exception as e:
        print(f"❌ Error al leer los comentarios: {e}")
        return

    process_tickets(document_text, tickets_to_find)
    export_results()
    print_statistics()

    not_found = tickets_to_find - all_ticket_ids
    if not_found:
        print("\n🚫 Tickets no encontrados:")
        for ticket in sorted(not_found):
            print(ticket)

if __name__ == '__main__':
    main()
