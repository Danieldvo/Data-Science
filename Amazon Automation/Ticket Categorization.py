import re
from collections import defaultdict
import pandas as pd
import os

# Rutas a los archivos
file_path = r'C:\Users\danivo\Desktop\Scripts\Error label analysis\look pattern\sim_comments_20250226(original).txt'
tickets_to_find_path = r'C:\Users\danivo\Desktop\Scripts\Error label analysis\look pattern\tickets_to_find_look_pattern.txt'

# Dictionary to store tickets by category
categorized_tickets = defaultdict(dict)

# Dictionary to store all categories for each ticket
ticket_categories = defaultdict(list)

# Set to keep track of all ticket IDs
all_ticket_ids = set()

patterns = {
    'Max_Capacity_Express_Services': [
        # UPS Express patterns
        r'(?i)ups_express_saver_eu_row',
        r'(?i)shipmethod:\s*ups_express',
        
        # Mondial Relay patterns
        r'(?i)mondial_relay_std_store',
        r'(?i)shipmethod:\s*mondial_relay',
        
        # Error messages for max capacity
        r'(?i)max\s+pickup\s+capacity\s+has\s+been\s+reached',
        r'(?i)maximum\s+capacity\s+for\s+given\s+ship-option',
        
        # Capacity measurement types
        r'(?i)capMeasurementType:\s*pkg_count',
        r'(?i)capMeasurementType:\s*cubic_volume',
        
        # Specific warehouses
        r'(?i)(?:fc|warehouse(?:\s+id)?):(?:\s*)(xfro|xfrs|xitk)',
        
        # Cancellation patterns
        r'(?i)cancel(?:led)?\s+(?:for|to)\s+(?:system\s+to\s+)?re-assign',
        r'(?i)shipment\s+(?:must\s+be\s+)?cancelled'
    ],
    
    'Delivery_Area_Restrictions': [
        # Specific delivery areas
        r'(?i)rapid_flood_03',
        r'(?i)christmas_markets_[a-z_]+',
        r'(?i)fr_mrela_38_quality',
        
        # General delivery area restrictions
        r'(?i)max\s+destination\s+capacity\s+has\s+been\s+reached\s+for\s+carrier\s+delivery\s+area',
        r'(?i)carrier\s+delivery\s+area:\s*([^\n]+)',
        
        # Affected warehouses
        r'(?i)(?:fc|warehouse(?:\s+id)?):(?:\s*)(xfrs|xfro|dqv6)',
        
        # Resolution patterns
        r'(?i)re-slam\s+after\s+cpt',
        r'(?i)late\s+slam',
        r'(?i)cancel(?:led)?\s+(?:for|to)\s+re-assign'
    ],
    
    'Capacity_Details': [
        # Detailed capacity constraints
        r'(?i)capacity(?:\s+has\s+been)?\s+reached\s+for\s+fc:([^\s]+)',
        r'(?i)shipMethod:([^\s]+)',
        r'(?i)capMeasurementType:([^\s]+)',
        
        # Processing capability
        r'(?i)processingCapabilityName:([^\s]+)',
        r'(?i)warehouseCycleName:([^\s]+)',
        
        # Destination constraints
        r'(?i)destinationWarehouseId:([^\s]+)',
        r'(?i)sortCode:([^\s]+)'
    ]
}

def read_tickets_to_find():
    """
    Lee los tickets del archivo tickets_to_find.txt
    """
    try:
        with open(tickets_to_find_path, 'r') as file:
            return set(line.strip() for line in file if line.strip())
    except FileNotFoundError:
        print(f"Error: El archivo {tickets_to_find_path} no fue encontrado.")
        return set()
    except Exception as e:
        print(f"Error al leer el archivo de tickets: {e}")
        return set()

def find_matching_patterns(text, pattern_list):
    """
    Find all matching patterns in the text, removing duplicates
    """
    matches = set()
    text_lower = text.lower()
    
    for pattern in pattern_list:
        found = re.finditer(pattern, text_lower)
        for match in found:
            match_text = text[match.start():match.end()]
            matches.add(match_text)
    
    return list(matches)

def categorize_ticket(ticket_text, ticket_id):
    """
    Categorize a single ticket based on its content and store matching patterns
    """
    all_ticket_ids.add(ticket_id)
    matched = False
    for category, pattern_list in patterns.items():
        matches = find_matching_patterns(ticket_text, pattern_list)
        if matches:
            categorized_tickets[category][ticket_id] = matches
            ticket_categories[ticket_id].append(category)
            matched = True
    
    if not matched:
        categorized_tickets['Unclassified'][ticket_id] = []
        ticket_categories[ticket_id].append('Unclassified')

def process_tickets(text, tickets_to_find):
    """
    Process the entire document and extract only specified tickets
    """
    tickets = re.split(r'=== TICKET: ([\w\-]+) ===', text)
    
    for i in range(1, len(tickets), 2):
        ticket_id = tickets[i]
        if ticket_id in tickets_to_find:
            ticket_content = tickets[i+1]
            categorize_ticket(ticket_content, ticket_id)
    
    return categorized_tickets

def export_to_csv(categorized_tickets):
    """
    Export the results to multiple CSV files with different views
    """
    output_dir = os.path.dirname(file_path)
    
    # Vista por categoría
    rows = []
    for category, tickets in categorized_tickets.items():
        for ticket_id, patterns in tickets.items():
            rows.append({
                'Category': category,
                'Ticket_ID': ticket_id,
                'Matching_Patterns': '; '.join(sorted(set(patterns))) if patterns else 'No patterns matched',
                'Total_Categories': len(ticket_categories[ticket_id]),
                'All_Categories': '; '.join(sorted(ticket_categories[ticket_id]))
            })
    
    df = pd.DataFrame(rows)
    category_file = os.path.join(output_dir, 'tickets_by_category.csv')
    df.to_csv(category_file, index=False)
    print(f"Category view exported to {category_file}")
    
    # Vista por ticket
    ticket_rows = []
    for ticket_id in all_ticket_ids:
        categories = ticket_categories[ticket_id]
        patterns_all = []
        for category in categories:
            if category != 'Unclassified':
                patterns_all.extend(categorized_tickets[category][ticket_id])
        
        ticket_rows.append({
            'Ticket_ID': ticket_id,
            'Number_of_Categories': len(categories),
            'Categories': '; '.join(sorted(categories)),
            'All_Patterns': '; '.join(sorted(set(patterns_all))) if patterns_all else 'No patterns matched'
        })
    
    df_tickets = pd.DataFrame(ticket_rows)
    ticket_file = os.path.join(output_dir, 'tickets_summary.csv')
    df_tickets.to_csv(ticket_file, index=False)
    print(f"Ticket summary exported to {ticket_file}")

def print_statistics():
    """
    Print detailed statistics about the categorization
    """
    print("\nDetailed Statistics:")
    print("-" * 50)
    
    # Tickets por categoría
    print("\nTickets por categoría:")
    for category in patterns.keys():
        count = len(categorized_tickets[category])
        print(f"{category}: {count}")
    
    # Tickets no clasificados
    unclassified_count = len(categorized_tickets['Unclassified'])
    print(f"Unclassified: {unclassified_count}")
    
    # Distribución de tickets por número de categorías
    category_counts = {}
    for ticket_id, categories in ticket_categories.items():
        num_categories = len(categories)
        category_counts[num_categories] = category_counts.get(num_categories, 0) + 1
    
    print("\nDistribución de tickets por número de categorías:")
    for num_categories, count in sorted(category_counts.items()):
        print(f"Tickets en {num_categories} categorías: {count}")
    
    # Porcentaje de te tickets clasificados y no clasificados
    total_tickets = len(all_ticket_ids)
    classified_tickets = total_tickets - unclassified_count
    print(f"\nTotal de tickets: {total_tickets}")
    print(f"Tickets clasificados: {classified_tickets} ({classified_tickets/total_tickets*100:.2f}%)")
    print(f"Tickets no clasificados: {unclassified_count} ({unclassified_count/total_tickets*100:.2f}%)")

def main():
    # Leer la lista de tickets a buscar
    tickets_to_find = read_tickets_to_find()
    if not tickets_to_find:
        print("No se encontraron tickets para buscar. El programa se detendrá.")
        return

    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            document_text = file.read()
    except FileNotFoundError:
        print(f"Error: The file {file_path} was not found.")
        return
    except Exception as e:
        print(f"An error occurred while reading the file: {e}")
        return

    # Process the document with filtered tickets
    results = process_tickets(document_text, tickets_to_find)

    # Export results
    export_to_csv(results)

    # Print statistics
    print_statistics()

    # Imprimir tickets que no se encontraron
    found_tickets = all_ticket_ids
    not_found = tickets_to_find - found_tickets
    if not_found:
        print("\nTickets no encontrados en el archivo original:")
        for ticket in not_found:
            print(ticket)

if __name__ == "__main__":
    main()
