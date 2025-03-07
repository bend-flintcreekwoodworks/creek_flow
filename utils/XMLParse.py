import xml.etree.ElementTree as ET
import csv
import os
import math
from math import gcd

# Use round-half-up instead of Python's default round (banker's rounding)
def round_half_up(x):
    return math.floor(x + 0.5)

# Simplify fractions for the fraction part (e.g. "1/16")
def simplify_fraction(numerator, denominator):
    common_divisor = gcd(numerator, denominator)
    numerator //= common_divisor
    denominator //= common_divisor
    return f"{numerator}/{denominator}" if denominator != 1 else str(numerator)

# Convert mm to inches, rounding to nearest 1/16 with round-half-up
def mm_to_inches_and_format(mm):
    if not mm:
        return "0"
    inches = float(mm) / 25.4
    # Multiply inches by 16 to get sixteenths
    sixteenths = inches * 16
    # Round half up
    rounded_sixteenths = round_half_up(sixteenths)
    whole_inch = rounded_sixteenths // 16
    fraction = rounded_sixteenths % 16
    if fraction == 0:
        return str(whole_inch)
    fraction_str = simplify_fraction(fraction, 16)
    return f"{whole_inch} {fraction_str}" if whole_inch else fraction_str

# Extract product details from XML
def extract_product_details(product):
    return {
        "UniqueID": product.get("UniqueID"),
        "CabNo": product.get("CabNo"),
        "ProdName": product.get("ProdName"),
        "Width": product.get("Width"),
        "Height": product.get("Height"),
        "Depth": product.get("Depth"),
        "CabProdParts": [
            {
                "ReportName": part.get("ReportName"),
                "W": part.get("W"),
                "L": part.get("L"),
                "Comment": part.get("Comment"),
            }
            for part in product.findall(".//CabProdPart")
        ],
    }

# Parse XML and save as CSV
def parse_xml_to_csv(xml_filepath, output_folder):
    with open(xml_filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Find where XML starts
    xml_content = None
    for i, line in enumerate(lines):
        if line.strip().startswith("<?xml"):
            xml_content = "".join(lines[i:])
            break

    if not xml_content:
        raise ValueError("No valid XML found in the file.")

    # Parse XML
    root = ET.fromstring(xml_content)
    room_unique_id = root.get("UniqueID")

    if not room_unique_id:
        raise ValueError("Room UniqueID not found in XML.")

    products_data = [extract_product_details(p) for p in root.findall(".//Product")]

    # Generate CSV filename
    csv_filename = f"Room_{room_unique_id}_parts.csv"
    csv_filepath = os.path.join(output_folder, csv_filename)

    with open(csv_filepath, mode="w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["Part Name", "Width (inches)", "Length (inches)", "Cabinet Number"])

        for product in products_data:
            for part in product["CabProdParts"]:
                width_str = mm_to_inches_and_format(part["W"])
                length_str = mm_to_inches_and_format(part["L"])
                writer.writerow([
                    part["ReportName"],
                    width_str,
                    length_str,
                    product["CabNo"]
                ])

    return csv_filepath
