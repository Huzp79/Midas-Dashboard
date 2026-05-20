import re

data = open('Midas_Brain/raw/market_data/latest_data.md', encoding='utf-8').read()
matches = re.findall(r'POI Bearish: OB\(([\d.]+)-([\d.]+)\)', data)
print('Found:', matches)