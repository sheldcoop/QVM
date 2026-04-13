"""Quick test to verify parser output against UL_1 data from file"""

from src.parser import parse_qvm_file
import json

# Parse the test file
df = parse_qvm_file('/Users/prince/Desktop/QVM/Post PFC_Pad to Via_Panel 20_B.txt')

# Filter for UL_1 only
ul1_data = df[df['Location'] == 'UL_1']

print("=" * 80)
print("PARSER OUTPUT FOR UL_1:")
print("=" * 80)
print(f"Number of rows for UL_1: {len(ul1_data)}")
print("\nRows:")
print(ul1_data.to_string())

print("\n" + "=" * 80)
print("FILE DATA FOR UL_1:")
print("=" * 80)
print("""
Circle: Pad_UL_1(ID:35, From 180 Pts.) 
     Diameter =         0.305259

Circle: Via_UL_1(ID:36, From 43 Pts.) 
     Diameter =         0.017521

Distance: PtV_UL_1(ID:37) between Via_UL_1b(ID:36) and Pad_UL_1b(ID:35)
           SC =         0.009098
           DX =         0.004573
           DY =        -0.007866
""")

print("\n" + "=" * 80)
print("EXPECTED BEHAVIOR:")
print("=" * 80)
print("Should have 1 row per location with BOTH Pad and Via diameters")
print("Current: 2 rows (one Pad, one Via)")
print("Which is correct? [depends on design intent]")
