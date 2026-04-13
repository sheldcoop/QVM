from src.parser import parse_qvm_file
import os

# Use full path to file
file_path = '/Users/prince/Desktop/QVM/Post PFC_Pad to Via_Panel 20_B.txt'

df = parse_qvm_file(file_path)

print("=" * 80)
print("PARSER OUTPUT - SIMPLIFIED COLUMNS")
print("=" * 80)

# Check if we have one row per location now
ul1 = df[df['Location'] == 'UL_1']
print(f"\nUL_1 now has: {len(ul1)} row(s)")
if len(ul1) > 0:
    print("\nColumns in DataFrame:")
    print(df.columns.tolist())
    print("\nUL_1 Data:")
    print(ul1.to_string())

print("\n" + "=" * 80)
print(f"Total rows in dataset: {len(df)}")
print(f"Unique locations: {df['Location'].nunique()}")
print("=" * 80)
