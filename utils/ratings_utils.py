"""
Utility functions for ratings conversion and processing
"""
from decimal import Decimal, ROUND_HALF_UP

def format_to_two_decimals(value):
    """Format a number to exactly 2 decimal places using Decimal for precision"""
    if value is None:
        return None
    # Convert to Decimal for precise formatting, then back to float
    decimal_val = Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return float(decimal_val)

def convert_rating_to_numeric(rating_text):
    """
    Convert text rating to numeric value based on the mapping:
    Strongly Agree -> 5.00
    Agree -> 4.50
    Neutral -> 4.00
    Disagree -> 2.00
    Strongly Disagree -> 1.00
    All values formatted to exactly 2 decimal places
    """
    if not rating_text or rating_text.strip() == '':
        return None
    
    rating_text = rating_text.strip()
    
    rating_map = {
        "Strongly Agree": 5.0,
        "Agree": 4.5,
        "Neutral": 4.0,
        "Disagree": 2.0,
        "Strongly Disagree": 1.0
    }
    
    result = rating_map.get(rating_text, None)
    return format_to_two_decimals(result) if result is not None else None

def calculate_average_rating(satisfied, topics, professor, materials):
    """
    Calculate average rating from the 4 numeric rating values
    Only includes non-None values in the calculation
    Formatted to exactly 2 decimal places
    """
    numeric_values = [v for v in [satisfied, topics, professor, materials] if v is not None]
    if numeric_values:
        average = sum(numeric_values) / len(numeric_values)
        return format_to_two_decimals(average)
    return None

def convert_ratings_to_numeric(satisfied_text, topics_text, professor_text, materials_text):
    """
    Convert all 4 text ratings to numeric and calculate average
    Returns tuple: (satisfied_numeric, topics_numeric, professor_numeric, materials_numeric, average_rating)
    """
    satisfied_numeric = convert_rating_to_numeric(satisfied_text)
    topics_numeric = convert_rating_to_numeric(topics_text)
    professor_numeric = convert_rating_to_numeric(professor_text)
    materials_numeric = convert_rating_to_numeric(materials_text)
    
    average_rating = calculate_average_rating(satisfied_numeric, topics_numeric, professor_numeric, materials_numeric)
    
    return satisfied_numeric, topics_numeric, professor_numeric, materials_numeric, average_rating
