#!/usr/bin/env python3
"""
LRS Reader Utilities
Helper functions for reading LRS Word documents.
"""

from docx import Document


def read_lrs_structure(filepath):
    """Read LRS document and return structure summary."""
    doc = Document(filepath)

    result = {
        'title': '',
        'sections': [],
        'tables': [],
        'functional_requirements': [],
        'interface_signals': []
    }

    # Get document title
    for para in doc.paragraphs[:5]:
        if para.text.strip() and 'Heading 1' in para.style.name:
            result['title'] = para.text.strip()
            break

    # Extract sections and content
    current_section = None
    for para in doc.paragraphs:
        if 'Heading' in para.style.name:
            if current_section:
                result['sections'].append(current_section)
            current_section = {
                'heading': para.text.strip(),
                'level': para.style.name,
                'content': []
            }
        elif current_section and para.text.strip():
            current_section['content'].append(para.text.strip())

    if current_section:
        result['sections'].append(current_section)

    # Extract tables
    for i, table in enumerate(doc.tables):
        table_data = []
        for row in table.rows:
            row_data = [cell.text.strip() for cell in row.cells]
            table_data.append(row_data)

        # Identify table type by headers
        if table_data:
            headers = table_data[0] if table_data else []
            table_info = {
                'index': i,
                'headers': headers,
                'rows': len(table_data) - 1,
                'data': table_data
            }

            # Classify table
            header_str = ' '.join(headers).lower()
            if '信号' in header_str or 'signal' in header_str:
                result['interface_signals'].extend(table_data[1:])
            elif 'opcode' in header_str or '命令' in header_str:
                result['functional_requirements'].extend(table_data[1:])

            result['tables'].append(table_info)

    return result


def extract_reset_requirements(lrs_data):
    """Extract reset-related requirements from LRS data."""
    reset_info = {
        'signals': [],
        'behavior': [],
        'registers': []
    }

    # Look for reset sections
    for section in lrs_data.get('sections', []):
        heading = section.get('heading', '').lower()
        if '复位' in heading or 'reset' in heading:
            reset_info['behavior'].extend(section.get('content', []))

    # Look for reset signals in tables
    for signal in lrs_data.get('interface_signals', []):
        if len(signal) >= 2:
            signal_name = str(signal[0]).lower() if signal[0] else ''
            if 'rst' in signal_name or 'reset' in signal_name or '复位' in signal_name:
                reset_info['signals'].append(signal)

    return reset_info


def extract_data_interface_requirements(lrs_data):
    """Extract data interface requirements from LRS data."""
    data_info = {
        'signals': [],
        'protocols': [],
        'timing': []
    }

    # Look for data interface sections
    for section in lrs_data.get('sections', []):
        heading = section.get('heading', '').lower()
        content = section.get('content', [])
        if '数据接口' in heading or 'data interface' in heading:
            data_info['protocols'].extend(content)
        if '时序' in heading or 'timing' in heading:
            data_info['timing'].extend(content)

    # Look for data signals in tables
    for signal in lrs_data.get('interface_signals', []):
        if len(signal) >= 2:
            signal_name = str(signal[0]).lower() if signal[0] else ''
            if any(x in signal_name for x in ['pdi', 'pdo', 'pcs', 'lane']):
                data_info['signals'].append(signal)

    return data_info


if __name__ == '__main__':
    import sys
    import json

    if len(sys.argv) < 3:
        print("Usage: python lrs_reader.py <command> <filepath> [args...]")
        print("Commands: read, reset, data_interface")
        sys.exit(1)

    command = sys.argv[1]
    filepath = sys.argv[2]

    if command == 'read':
        result = read_lrs_structure(filepath)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif command == 'reset':
        lrs_data = read_lrs_structure(filepath)
        result = extract_reset_requirements(lrs_data)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif command == 'data_interface':
        lrs_data = read_lrs_structure(filepath)
        result = extract_data_interface_requirements(lrs_data)
        print(json.dumps(result, ensure_ascii=False, indent=2))
