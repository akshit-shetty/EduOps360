#!/usr/bin/env python3
"""
Debug script to analyze session data and date issues
"""
import pandas as pd
from datetime import datetime, timedelta
import sys
import os

def analyze_session_data(file_path):
    """Analyze the session data to understand date issues"""
    
    print("🔍 ANALYZING SESSION DATA")
    print("=" * 50)
    
    try:
        # Load the Excel file
        print(f"📂 Loading file: {file_path}")
        df = pd.read_excel(file_path, engine='openpyxl')
        
        print(f"📊 DataFrame shape: {df.shape}")
        print(f"📋 Columns: {list(df.columns)}")
        
        # Analyze Date column before conversion
        print("\n📅 DATE COLUMN ANALYSIS (BEFORE CONVERSION)")
        print("-" * 40)
        print("Sample date values:")
        for i, date_val in enumerate(df['Date'].head(10)):
            print(f"  Row {i}: '{date_val}' (type: {type(date_val)})")
        
        print(f"\nUnique date values: {df['Date'].nunique()}")
        print(f"Null/NaN dates: {df['Date'].isna().sum()}")
        
        # Convert dates and analyze
        df['Date_Original'] = df['Date']  # Keep original
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        
        print("\n📅 DATE COLUMN ANALYSIS (AFTER CONVERSION)")
        print("-" * 40)
        print(f"Successfully converted dates: {df['Date'].notna().sum()}")
        print(f"Failed conversions (NaN): {df['Date'].isna().sum()}")
        
        # Show valid dates
        valid_dates = df[df['Date'].notna()]
        if not valid_dates.empty:
            print(f"\nValid date range:")
            print(f"  Earliest: {valid_dates['Date'].min()}")
            print(f"  Latest: {valid_dates['Date'].max()}")
            
            print(f"\nValid dates by day of week:")
            for day_name, count in valid_dates['Date'].dt.day_name().value_counts().items():
                print(f"  {day_name}: {count} sessions")
        
        # Show failed conversions
        failed_dates = df[df['Date'].isna()]
        if not failed_dates.empty:
            print(f"\n❌ FAILED DATE CONVERSIONS:")
            print("-" * 30)
            for i, orig_date in enumerate(failed_dates['Date_Original'].head(10)):
                print(f"  Row {failed_dates.index[i]}: '{orig_date}' (type: {type(orig_date)})")
        
        # Analyze current weekend filtering logic
        today = datetime.today().date()
        print(f"\n📆 WEEKEND FILTERING ANALYSIS")
        print("-" * 30)
        print(f"Today: {today} ({today.strftime('%A')})")
        
        if today.weekday() >= 4:  # Friday (4), Saturday (5), Sunday (6)
            next_friday = today - timedelta(days=today.weekday() - 4)
        else:
            days_ahead = (4 - today.weekday() + 7) % 7
            next_friday = today + timedelta(days=days_ahead)
        
        end_of_weekend = next_friday + timedelta(days=2)
        
        print(f"Target weekend: {next_friday} to {end_of_weekend}")
        
        # Check how many sessions fall in this weekend
        weekend_sessions = df[(df['Date'].dt.date >= next_friday) & (df['Date'].dt.date <= end_of_weekend)]
        print(f"Sessions in target weekend: {len(weekend_sessions)}")
        
        # Show all sessions by date
        print(f"\n📋 ALL SESSIONS BY DATE:")
        print("-" * 25)
        valid_sessions = df[df['Date'].notna()].copy()
        if not valid_sessions.empty:
            for date, group in valid_sessions.groupby(valid_sessions['Date'].dt.date):
                print(f"  {date} ({date.strftime('%A')}): {len(group)} sessions")
                for _, row in group.iterrows():
                    print(f"    - {row['Topic']} ({row['SME_Prof_Name']})")
        
        # Email analysis
        print(f"\n📧 EMAIL ANALYSIS:")
        print("-" * 15)
        print(f"Total unique professors: {df['SME_Prof_Name'].nunique()}")
        print(f"Total unique emails: {df['Email'].nunique()}")
        print(f"Rows with valid emails: {df['Email'].notna().sum()}")
        
        # Recommendations
        print(f"\n💡 RECOMMENDATIONS:")
        print("-" * 15)
        
        if df['Date'].isna().sum() > 0:
            print("1. ⚠️  Fix date format issues:")
            print("   - Check Excel date formatting")
            print("   - Ensure dates are in recognizable format (YYYY-MM-DD, MM/DD/YYYY, etc.)")
            print("   - Remove any text or special characters from date cells")
        
        if len(weekend_sessions) == 0:
            print("2. 📅 No sessions found for target weekend:")
            print(f"   - Current filter looks for {next_friday} to {end_of_weekend}")
            print("   - Consider modifying date range or using all sessions")
            print("   - Or update Excel file with sessions for the target weekend")
        
        if df['Email'].isna().sum() > 0:
            print("3. 📧 Fix missing email addresses")
        
        return {
            'total_rows': len(df),
            'valid_dates': df['Date'].notna().sum(),
            'invalid_dates': df['Date'].isna().sum(),
            'weekend_sessions': len(weekend_sessions),
            'unique_professors': df['SME_Prof_Name'].nunique(),
            'unique_emails': df['Email'].nunique()
        }
        
    except Exception as e:
        print(f"❌ Error analyzing file: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    # Look for Excel files in current directory
    excel_files = [f for f in os.listdir('.') if f.endswith(('.xlsx', '.xls'))]
    
    if excel_files:
        print("📁 Found Excel files:")
        for i, file in enumerate(excel_files):
            print(f"  {i+1}. {file}")
        
        if len(excel_files) == 1:
            analyze_session_data(excel_files[0])
        else:
            print("\n🔍 Analyzing first Excel file found...")
            analyze_session_data(excel_files[0])
    else:
        print("❌ No Excel files found in current directory")
        print("💡 Place your Excel file in the same directory as this script")
