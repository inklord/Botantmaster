import pandas as pd
import os
from datetime import datetime

def process_orders(input_file):
    # Read the CSV file
    df = pd.read_csv(input_file)
    
    # Translation dictionaries
    payment_status_translation = {
        'paid': 'Pagado',
        'voided': 'Anulado',
        'pending': 'Pendiente',
        'refunded': 'Reembolsado',
        'partially_refunded': 'Reembolsado Parcialmente'
    }
    
    fulfillment_status_translation = {
        'fulfilled': 'Enviado',
        'unfulfilled': 'Pendiente de Envío',
        'partial': 'Envío Parcial'
    }
    
    # Translate status columns
    df['Financial Status'] = df['Financial Status'].map(payment_status_translation).fillna(df['Financial Status'])
    df['Fulfillment Status'] = df['Fulfillment Status'].map(fulfillment_status_translation).fillna(df['Fulfillment Status'])
    
    # Convert date columns to datetime and format them
    date_columns = ['Paid at', 'Created at']
    for col in date_columns:
        try:
            df[col] = pd.to_datetime(df[col], utc=True).dt.strftime('%d/%m/%Y %H:%M')
        except:
            df[col] = df[col]
    
    # Group by order number and aggregate line items
    grouped = df.groupby('Name', as_index=False).agg({
        'Email': 'first',
        'Financial Status': 'first',
        'Paid at': 'first',
        'Fulfillment Status': 'first',
        'Total': 'first',
        'Discount Code': 'first',
        'Discount Amount': 'first',
        'Lineitem name': lambda x: ' • '.join(filter(None, x)),  # Cambio a bullet points
        'Lineitem quantity': 'sum',
        'Lineitem price': 'sum',
        'Billing Name': 'first',
        'Billing City': 'first',
        'Billing Country': 'first',
        'Shipping Method': 'first',
        'Created at': 'first',
        'Payment Method': 'first'
    })
    
    # Rename columns for clarity
    grouped.columns = [
        'Nº Pedido',
        'Email',
        'Estado',
        'Fecha Pago',
        'Envío',
        'Total',
        'Cupón',
        'Descuento',
        'Productos',
        'Cantidad',
        'Subtotal',
        'Cliente',
        'Ciudad',
        'País',
        'Método Envío',
        'Fecha Pedido',
        'Método Pago'
    ]
    
    # Sort by order number (descending)
    grouped['Nº Pedido'] = grouped['Nº Pedido'].str.replace('#', '').astype(int)
    grouped = grouped.sort_values('Nº Pedido', ascending=False)
    grouped['Nº Pedido'] = '#' + grouped['Nº Pedido'].astype(str).str.zfill(4)  # Padding con ceros
    
    # Format currency columns
    for col in ['Total', 'Descuento', 'Subtotal']:
        grouped[col] = pd.to_numeric(grouped[col], errors='coerce').fillna(0)
    
    # Save to Excel file
    output_file = os.path.join(os.path.dirname(input_file), 'pedidos_organizados.xlsx')
    
    # Create Excel writer with xlsxwriter engine
    writer = pd.ExcelWriter(output_file, engine='xlsxwriter')
    
    # Write to Excel
    grouped.to_excel(writer, sheet_name='Pedidos', index=False)
    
    # Get workbook and worksheet objects
    workbook = writer.book
    worksheet = writer.sheets['Pedidos']
    
    # Define formats
    header_format = workbook.add_format({
        'bold': True,
        'bg_color': '#2F5597',  # Azul más profesional
        'font_color': 'white',
        'border': 0,
        'text_wrap': True,
        'align': 'center',
        'valign': 'vcenter',
        'font_size': 11,
        'font_name': 'Segoe UI',
        'bottom': 2,
        'bottom_color': '#1F3864'  # Borde inferior más oscuro
    })
    
    currency_format = workbook.add_format({
        'num_format': '_-* #,##0.00 €_-;-* #,##0.00 €_-;_-* "-"?? €_-;_-@_-',
        'align': 'right',
        'valign': 'vcenter',
        'font_name': 'Segoe UI',
        'font_size': 10,
        'border_color': '#E0E0E0'
    })
    
    date_format = workbook.add_format({
        'num_format': 'dd/mm/yyyy hh:mm',
        'align': 'center',
        'valign': 'vcenter',
        'font_name': 'Segoe UI',
        'font_size': 10,
        'border_color': '#E0E0E0'
    })
    
    text_format = workbook.add_format({
        'align': 'left',
        'valign': 'vcenter',
        'text_wrap': True,
        'font_name': 'Segoe UI',
        'font_size': 10,
        'border_color': '#E0E0E0'
    })
    
    center_format = workbook.add_format({
        'align': 'center',
        'valign': 'vcenter',
        'font_name': 'Segoe UI',
        'font_size': 10,
        'border_color': '#E0E0E0'
    })
    
    status_format = workbook.add_format({
        'align': 'center',
        'valign': 'vcenter',
        'font_name': 'Segoe UI',
        'font_size': 10,
        'border_color': '#E0E0E0'
    })
    
    # Set specific column widths
    column_widths = {
        'Nº Pedido': 10,
        'Email': 35,
        'Estado': 12,
        'Fecha Pago': 18,
        'Envío': 12,
        'Total': 12,
        'Cupón': 15,
        'Descuento': 12,
        'Productos': 60,
        'Cantidad': 10,
        'Subtotal': 12,
        'Cliente': 35,
        'Ciudad': 18,
        'País': 8,
        'Método Envío': 15,
        'Fecha Pedido': 18,
        'Método Pago': 15
    }
    
    # Apply formats to columns
    for idx, col in enumerate(grouped.columns):
        width = column_widths.get(col, 15)
        
        if col in ['Total', 'Descuento', 'Subtotal']:
            worksheet.set_column(idx, idx, width, currency_format)
        elif col in ['Fecha Pago', 'Fecha Pedido']:
            worksheet.set_column(idx, idx, width, date_format)
        elif col in ['Nº Pedido', 'Cantidad', 'País']:
            worksheet.set_column(idx, idx, width, center_format)
        elif col in ['Estado', 'Envío']:
            worksheet.set_column(idx, idx, width, status_format)
        elif col == 'Productos':
            product_format = workbook.add_format({
                'align': 'left',
                'valign': 'vcenter',
                'text_wrap': True,
                'font_name': 'Segoe UI',
                'font_size': 10,
                'border_color': '#E0E0E0'
            })
            worksheet.set_column(idx, idx, width, product_format)
        else:
            worksheet.set_column(idx, idx, width, text_format)
    
    # Write headers
    for col_num, value in enumerate(grouped.columns.values):
        worksheet.write(0, col_num, value, header_format)
    
    # Add alternating row colors and conditional formatting
    row_even_format = workbook.add_format({
        'bg_color': '#F9F9F9',
        'font_name': 'Segoe UI',
        'font_size': 10,
        'border_color': '#E0E0E0'
    })
    
    # Conditional formatting for status columns
    worksheet.conditional_format('C2:C1000', {
        'type': 'text',
        'criteria': 'containing',
        'value': 'Pagado',
        'format': workbook.add_format({
            'bg_color': '#E8F5E9',
            'font_color': '#2E7D32',
            'bold': True
        })
    })
    
    worksheet.conditional_format('C2:C1000', {
        'type': 'text',
        'criteria': 'containing',
        'value': 'Anulado',
        'format': workbook.add_format({
            'bg_color': '#FFEBEE',
            'font_color': '#C62828',
            'bold': True
        })
    })
    
    worksheet.conditional_format('E2:E1000', {
        'type': 'text',
        'criteria': 'containing',
        'value': 'Enviado',
        'format': workbook.add_format({
            'bg_color': '#E3F2FD',
            'font_color': '#1565C0',
            'bold': True
        })
    })
    
    worksheet.conditional_format('E2:E1000', {
        'type': 'text',
        'criteria': 'containing',
        'value': 'Pendiente de Envío',
        'format': workbook.add_format({
            'bg_color': '#FFF3E0',
            'font_color': '#EF6C00',
            'bold': True
        })
    })
    
    # Set row height
    worksheet.set_default_row(22)  # Altura más compacta
    worksheet.set_row(0, 32)  # Header más alto
    
    # Show subtle gridlines
    worksheet.hide_gridlines(2)  # 2 = show only page gridlines
    
    # Freeze panes and zoom
    worksheet.freeze_panes(1, 1)
    worksheet.set_zoom(90)  # Zoom out slightly for better overview
    
    # Add sheet protection with exceptions
    worksheet.protect('', {
        'format_columns': True,
        'format_rows': True,
        'sort': True,
        'autofilter': True
    })
    
    # Add autofilter
    worksheet.autofilter(0, 0, len(grouped), len(grouped.columns) - 1)
    
    # Save the Excel file
    writer.close()
    
    print(f"Pedidos organizados y guardados en: {output_file}")
    print(f"Total de pedidos procesados: {len(grouped)}")

if __name__ == "__main__":
    input_file = r"C:\Users\mario\Downloads\orders_export_1.csv"
    process_orders(input_file) 