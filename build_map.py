import csv
import json
import urllib.request
import time
import os
import ssl

def get_coordinates(country):
    """Fetches coordinates for a country based on its name using Nominatim (OpenStreetMap)."""
    try:
        import urllib.parse
        safe_country = urllib.parse.quote(country)
        url = f"https://nominatim.openstreetmap.org/search?country={safe_country}&format=json&limit=1"
        req = urllib.request.Request(url, headers={'User-Agent': 'mapbox-storytelling-builder/1.0'})
        
        # Bypass SSL verification (common issue on macOS Python installations)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        with urllib.request.urlopen(req, context=ctx) as response:
            data = json.loads(response.read().decode())
            if len(data) > 0:
                # Nominatim returns lat, lon
                return [float(data[0]['lon']), float(data[0]['lat'])]
            return [0, 0]
    except Exception as e:
        print(f"⚠️ Could not fetch coords for {country}: {e}")
        return [0, 0]

def get_color_for_gap(gap_val, max_gap):
    # Scale intensity from 0 to 1 based on gap relative to max_gap
    intensity = min(abs(gap_val) / max_gap, 1.0) if max_gap > 0 else 0
    
    if gap_val >= 0:
        # Positive: Red (More female insecurity)
        # Intensity increases darkness
        r = int(255 - (100 * intensity))
        g = int(200 * (1 - intensity))
        b = int(200 * (1 - intensity))
    else:
        # Negative: Blue (More male insecurity)
        r = int(200 * (1 - intensity))
        g = int(200 * (1 - intensity))
        b = int(255 - (100 * intensity))
        
    return f"rgb({r}, {g}, {b})"

def main():
    csv_file = "data.csv"
    output_file = "config.js"
    
    if not os.path.exists(csv_file):
        print(f"❌ Error: '{csv_file}' not found in the current directory.")
        return

    print("🌍 Reading data.csv and fetching coordinates...")
    rows = []
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Fuzzy match gap column
            gap_key = next((k for k in row.keys() if k and 'gap' in k.lower()), 'Gap (Female - Male, pp)')
            try:
                # Convert gap to float for sorting and coloring
                gap_str = row.get(gap_key, '0').replace('%', '').strip()
                gap_val = float(gap_str) if gap_str else 0.0
            except ValueError:
                gap_val = 0.0
                
            row['gap_val'] = gap_val
            row['gap_key'] = gap_key  # Save the key so we can grab the original string later
            rows.append(row)
            
    # 1. SORTING: Order by MAGNITUDE of gap (absolute value), from greatest to least
    rows.sort(key=lambda x: abs(x['gap_val']), reverse=True)
    
    # Find max gap magnitude for color scaling
    max_gap = max([abs(r['gap_val']) for r in rows]) if rows else 1.0
    if max_gap == 0: max_gap = 1.0

    choropleth_colors = ["match", ["get", "ISO_A3"]]
    chapters = []
    for row in rows:
        # Fuzzy match columns
        country = next((row[k] for k in row.keys() if k and 'country' in k.lower()), 'Unknown')
        iso3 = next((row[k] for k in row.keys() if k and 'iso' in k.lower()), '')
        
        female = 'N/A'
        male = 'N/A'
        for k in row.keys():
            if not k: continue
            k_lower = k.lower()
            # If it has female but not gap
            if 'female' in k_lower and 'gap' not in k_lower:
                female = row[k]
            # If it has male but not female and not gap
            elif 'male' in k_lower and 'female' not in k_lower and 'gap' not in k_lower:
                male = row[k]
                
        gap = row.get(row.get('gap_key', ''), 'N/A')
        gap_val = row['gap_val']
        
        if not iso3:
            continue
            
        print(f"  -> Processing {country} ({iso3}), Gap: {gap_val}...")
        lnglat = get_coordinates(country)
        time.sleep(1.2) # Nominatim requires 1 request per second max
        
        # Calculate dynamic background color based on gap
        bg_color = get_color_for_gap(gap_val, max_gap)
        choropleth_colors.extend([iso3.upper(), bg_color])
        
        description = f"""
        <h3 style="margin-top: 0;">Water Insecurity in {country}</h3>
        <ul style="font-size: 1.1em; padding: 15px; background: rgba(0,0,0,0.15); border-radius: 8px; list-style-type: none; margin-left: 0;">
            <li><b>Female:</b> {female} pp</li>
            <li><b>Male:</b> {male} pp</li>
            <li><b>Gap (Female - Male):</b> {gap} pp</li>
        </ul>
        <p><i>{"Red indicates higher female insecurity." if gap_val >= 0 else "Blue indicates higher male insecurity."}</i></p>
        """
        
        chapter = {
            'id': iso3.lower(),
            'alignment': 'left',
            'hidden': False,
            'title': country,
            'image': '',
            'description': description,
            'bgColor': bg_color,  # Custom property for our updated index.html
            'location': {
                'center': lnglat,
                'zoom': 6.5,   # Zoomed in closer for a more dynamic effect
                'pitch': 45.0,
                'bearing': 0.0,
                'speed': 0.5,  # Slows down the flight slightly for a cinematic feel
                'curve': 1.5   # Adds a more pronounced zoom-out/zoom-in curve during the flight
            },
            'mapAnimation': 'flyTo',
            'rotateAnimation': False,
            'onChapterEnter': [],
            'onChapterExit': []
        }
        chapters.append(chapter)

    choropleth_colors.append("rgba(0,0,0,0)") # Fallback color

    # Try to preserve existing access token if config.js already exists
    access_token = 'YOUR_MAPBOX_ACCESS_TOKEN'
    if os.path.exists(output_file):
        with open(output_file, 'r', encoding='utf-8') as old_f:
            old_content = old_f.read()
            import re
            match = re.search(r"accessToken:\s*['\"]([^'\"]+)['\"]", old_content)
            if match and match.group(1) != 'YOUR_MAPBOX_ACCESS_TOKEN':
                access_token = match.group(1)

    # Now generate the config.js file
    config_content = f"""var config = {{
    style: 'mapbox://styles/mapbox/light-v11',
    accessToken: '{access_token}',
    showMarkers: true,
    markerColor: '#3FB1CE',
    theme: 'light',
    use3dTerrain: false,
    title: 'Water Security Overview',
    subtitle: 'Exploring the gender gap in water insecurity.',
    byline: 'By Jaimie Chun',
    footer: 'Data source: Your private dataset',
    choroplethColors: {json.dumps(choropleth_colors, indent=4)},
    chapters: {json.dumps(chapters, indent=4)}
}};"""

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(config_content)
        
    print(f"\n✅ Success! Generated '{output_file}' with {len(chapters)} chapters.")
    print("👉 Don't forget to replace 'YOUR_MAPBOX_ACCESS_TOKEN' in config.js with your actual token!")

if __name__ == "__main__":
    main()
