"""
TripIt Flight Exporter
======================
This script automatically extracts all your flight data from TripIt and saves it to a CSV file.

What it does:
1. Opens TripIt in a browser (you log in manually)
2. Navigates through all your trips (handles pagination automatically)
3. Visits each trip detail page
4. Extracts flight information using Claude AI
5. Saves everything to flights_export.csv

Requirements:
- Python 3.8 or newer
- Playwright browser automation library
- Claude API key (get from console.anthropic.com)
"""

import asyncio
import csv
import json
import os
import re
from playwright.async_api import async_playwright
import anthropic

# ============================================================================
# CONFIGURATION - EDIT THESE VALUES
# ============================================================================

# Your Claude API key - get it from: https://console.anthropic.com/settings/keys
CLAUDE_API_KEY = "your-api-key-hereyour-api-key-here"

# Output CSV file name
OUTPUT_FILE = "flights_export.csv"

# TripIt URLs
# Change this to "upcoming" if you want upcoming trips instead of past trips
TRIPS_FILTER = "past"  # Options: "past" or "upcoming"
TRIPS_LIST_URL = f"https://www.tripit.com/app/trips?trips_filter={TRIPS_FILTER}&page=1"

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def wait_for_manual_login(page):
    """
    Waits for you to manually log into TripIt.
    Press Enter in the terminal once you're logged in and see your trips list.
    """
    print("\n" + "="*70)
    print("MANUAL LOGIN REQUIRED")
    print("="*70)
    print("1. A browser window has opened to TripIt")
    print("2. Please log in with your credentials")
    print("3. Wait until you see your trips list")
    print("4. Then come back here and press ENTER to continue")
    print("="*70 + "\n")
    
    input("Press ENTER once you're logged in and see your trips list...")
    
    # Wait a moment for page to fully load
    await asyncio.sleep(2)
    print("✓ Continuing with export...\n")


async def get_all_trip_urls(page):
    """
    Navigates through all pages of trips and collects URLs to each trip detail page.
    Handles pagination automatically by incrementing page number in URL.
    """
    print("📋 Collecting trip URLs from all pages...")
    
    trip_urls = []
    page_number = 1
    base_url = "https://www.tripit.com/app/trips?trips_filter=past&page="
    
    while True:
        current_url = f"{base_url}{page_number}"
        print(f"   Scanning page {page_number}...")
        
        # Navigate to the specific page
        await page.goto(current_url, wait_until="domcontentloaded", timeout=15000)
        
        # Wait for trip cards to load - look for the specific data attribute from the HTML
        try:
            await page.wait_for_selector('a[data-cy="trip-list-item-name"]', timeout=10000)
            print(f"   DEBUG: Trip cards found, waiting for content to load...")
            await asyncio.sleep(2)  # Give page time to fully render
        except:
            print(f"   DEBUG: No trip cards found on this page")
            break  # No more trips, we've reached the end
        
        # Extract all trip URLs on current page
        # TripIt uses links like /app/trips/UUID inside cards with data-cy="trip-list-item-name"
        links = await page.evaluate('''
            () => {
                // Look specifically for trip name links
                const tripNameLinks = Array.from(document.querySelectorAll('a[data-cy="trip-list-item-name"]'));
                console.log('Found trip name links:', tripNameLinks.length);
                
                const hrefs = tripNameLinks.map(link => link.href);
                console.log('Trip URLs:', hrefs);
                return hrefs;
            }
        ''')
        
        print(f"   DEBUG: Raw links found: {links}")
        
        # If no trips found on this page, we're done
        if not links or len(links) == 0:
            print(f"   No trips found on page {page_number}, stopping pagination")
            break
        
        # Remove duplicates and add to our list
        unique_links = list(set(links))
        new_trips = [url for url in unique_links if url not in trip_urls]
        trip_urls.extend(new_trips)
        
        print(f"   Found {len(new_trips)} trips on this page")
        
        # Move to next page
        page_number += 1
        await asyncio.sleep(1)  # Be nice to the server
    
    print(f"✓ Found {len(trip_urls)} total trips across {page_number - 1} page(s)\n")
    return trip_urls


async def extract_flights_from_trip(page, trip_url, claude_client):
    """
    Visits a single trip detail page and uses Claude to extract flight information.
    Returns a list of flight dictionaries.
    """
    print(f"   Visiting: {trip_url}")
    
    try:
        # Navigate with a more lenient wait strategy
        await page.goto(trip_url, wait_until="domcontentloaded", timeout=15000)
        
        # Wait for the trip content to load
        await page.wait_for_selector('[data-cy="trip-date-span"]', timeout=10000)
        await asyncio.sleep(2)  # Give it a moment for any dynamic content
        
        # Get the trip name from the header
        trip_name = await page.evaluate('''
            () => {
                // Try multiple selectors to find the trip name
                let name = document.querySelector('h1')?.textContent?.trim();
                if (!name || name === '') {
                    name = document.querySelector('[data-cy="trip-list-item-name"]')?.textContent?.trim();
                }
                if (!name || name === '') {
                    name = document.querySelector('a[class*="tripName"]')?.textContent?.trim();
                }
                return name || 'Unknown Trip';
            }
        ''')
        
        print(f"   Trip name: {trip_name}")
        
        # Get the visible text content (more efficient than HTML for Claude)
        trip_text = await page.evaluate('''
            () => {
                const main = document.querySelector('main, [role="main"], .container');
                return main ? main.innerText : document.body.innerText;
            }
        ''')
        
        print(f"   DEBUG: Text length: {len(trip_text)}")
        
        # Use Claude to extract flight information
        flights = await extract_flights_with_claude(claude_client, trip_name, trip_text)
        
        if flights:
            print(f"   ✓ Extracted {len(flights)} flight(s)")
        else:
            print(f"   ℹ No flights found")
        
        return flights
        
    except Exception as e:
        print(f"   ✗ Error processing trip: {str(e)}")
        return []


async def extract_flights_with_claude(claude_client, trip_name, text_content):
    """
    Sends the trip text to Claude API and asks it to extract flight information.
    Returns a list of flight dictionaries.
    """
    
    prompt = f"""You are extracting flight information from a TripIt trip page.

Trip Name: {trip_name}

Here is the visible text from the page:
{text_content[:10000]}

Please extract ONLY flight information. Ignore hotels, cars, and other activities.

For each flight segment, extract:
- flight_date: in YYYY-MM-DD format (look for dates like "Thu, Nov 6" and convert to "2025-11-06")
- flight_time: departure time with timezone (e.g., "9:23 PM PST")
- origin: origin airport IATA code (e.g., "SFO")
- destination: destination airport IATA code (e.g., "PIT")
- flight_number: airline code + number (e.g., "UA794")

Important notes:
- Look for text like "SFO - PIT" which indicates origin and destination
- Look for "Flight Number UA 794" or similar
- Each connecting flight should be a separate entry
- Ignore layover/connection time entries
- If you see no flights at all, return an empty array []

Return your response as a JSON array of objects ONLY. No explanation, just the JSON.

Example format:
[
  {{
    "flight_date": "2025-11-06",
    "flight_time": "9:23 PM PST",
    "origin": "SFO",
    "destination": "PIT",
    "flight_number": "UA794"
  }}
]
"""

    try:
        message = claude_client.messages.create(
            model="claude-haiku-4-5-20251001",  # Using Haiku for cost efficiency
            max_tokens=2000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        response_text = message.content[0].text
        
        # Extract JSON from response (Claude might add explanation around it)
        json_match = re.search(r'\[[\s\S]*\]', response_text)
        if json_match:
            flights_data = json.loads(json_match.group())
            
            # Add trip_name to each flight
            for flight in flights_data:
                flight['trip_name'] = trip_name
            
            return flights_data
        else:
            return []
            
    except Exception as e:
        print(f"   ✗ Claude API error: {str(e)}")
        return []


async def save_to_csv(flights, output_file):
    """
    Saves all extracted flights to a CSV file, sorted by date/time in descending order.
    CSV format matches OpenFlights schema with most fields left blank for manual entry.
    """
    if not flights:
        print("⚠ No flights to save!")
        return
    
    # Sort flights by date and time in descending order (most recent first)
    def parse_datetime(flight):
        try:
            # Parse the date
            date_str = flight['flight_date']
            # Parse the time (extract just the time part, ignore timezone)
            time_str = flight['flight_time'].split()[0] + ' ' + flight['flight_time'].split()[1]
            datetime_str = f"{date_str} {time_str}"
            
            from datetime import datetime
            return datetime.strptime(datetime_str, "%Y-%m-%d %I:%M %p")
        except:
            # If parsing fails, put it at the end
            from datetime import datetime
            return datetime.min
    
    flights.sort(key=parse_datetime, reverse=True)
    
    # OpenFlights-compatible CSV format
    fieldnames = ['Date', 'From', 'To', 'Flight_Number', 'Airline', 'Distance', 'Duration', 
                  'Seat', 'Seat_Type', 'Class', 'Reason', 'Plane', 'Registration', 'Trip', 
                  'Note', 'From_OID', 'To_OID', 'Airline_OID', 'Plane_OID']
    
    # Prepare rows with OpenFlights format
    csv_rows = []
    for flight in flights:
        csv_rows.append({
            'Date': flight['flight_date'],
            'From': flight['origin'],
            'To': flight['destination'],
            'Flight_Number': flight['flight_number'],
            'Airline': '',
            'Distance': '',
            'Duration': '',
            'Seat': '',
            'Seat_Type': '',
            'Class': '',
            'Reason': '',
            'Plane': '',
            'Registration': '',
            'Trip': '',
            'Note': '',
            'From_OID': '',
            'To_OID': '',
            'Airline_OID': '',
            'Plane_OID': ''
        })
    
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_rows)
    
    print(f"\n✓ Successfully exported {len(flights)} flights to {output_file}")
    print(f"  (Sorted by date/time, most recent first)")
    print(f"  (CSV format: OpenFlights schema with Date, From, To, Flight_Number populated)")
    
    # Print a readable verification table
    print("\n" + "="*120)
    print("EXTRACTED FLIGHTS - VERIFICATION TABLE (Most Recent First)")
    print("="*120)
    print(f"{'Trip Name':<35} {'Date':<12} {'Time':<15} {'Route':<12} {'Flight':<10}")
    print("-"*120)
    
    for flight in flights:
        trip_name = flight['trip_name'][:33] + '..' if len(flight['trip_name']) > 35 else flight['trip_name']
        route = f"{flight['origin']} → {flight['destination']}"
        print(f"{trip_name:<35} {flight['flight_date']:<12} {flight['flight_time']:<15} {route:<12} {flight['flight_number']:<10}")
    
    print("="*120 + "\n")
    
    # Print a readable table
    print("\n" + "="*120)
    print("EXTRACTED FLIGHTS (Most Recent First)")
    print("="*120)
    print(f"{'Trip Name':<35} {'Date':<12} {'Time':<15} {'Route':<12} {'Flight':<10}")
    print("-"*120)
    
    for flight in flights:
        trip_name = flight['trip_name'][:33] + '..' if len(flight['trip_name']) > 35 else flight['trip_name']
        route = f"{flight['origin']} → {flight['destination']}"
        print(f"{trip_name:<35} {flight['flight_date']:<12} {flight['flight_time']:<15} {route:<12} {flight['flight_number']:<10}")
    
    print("="*120 + "\n")


# ============================================================================
# MAIN SCRIPT
# ============================================================================

async def main():
    """
    Main function that orchestrates the entire export process.
    """
    
    print("\n" + "="*70)
    print("TripRip - TripIt Flight Exporter")
    print("="*70 + "\n")
    
    # Validate API key
    if CLAUDE_API_KEY == "your-api-key-here":
        print("❌ ERROR: Please set your Claude API key in the script!")
        print("   Get your API key from: https://console.anthropic.com/settings/keys")
        print("   Then edit this script and replace 'your-api-key-here' with your actual key.")
        return
    
    # Initialize Claude client
    claude_client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    
    # Start Playwright
    async with async_playwright() as p:
        print("🚀 Launching browser...")
        browser = await p.chromium.launch(headless=False)  # headless=False so you can see it
        page = await browser.new_page()
        
        # Navigate to TripIt
        print(f"🌐 Opening TripIt: {TRIPS_LIST_URL}")
        await page.goto(TRIPS_LIST_URL)
        
        # Wait for manual login
        await wait_for_manual_login(page)
        
        # Get all trip URLs
        trip_urls = await get_all_trip_urls(page)
        
        if not trip_urls:
            print("❌ No trips found! Make sure you're logged in correctly.")
            await browser.close()
            return
        
        # Extract flights from each trip
        print(f"✈️  Processing {len(trip_urls)} trips...\n")
        all_flights = []
        
        for i, trip_url in enumerate(trip_urls, 1):
            print(f"[{i}/{len(trip_urls)}]")
            flights = await extract_flights_from_trip(page, trip_url, claude_client)
            all_flights.extend(flights)
            
            # Small delay to be respectful to the server
            await asyncio.sleep(1)
        
        # Save results
        await save_to_csv(all_flights, OUTPUT_FILE)
        
        print("\n🎉 Export complete!")
        print(f"📄 Results saved to: {OUTPUT_FILE}")
        
        # Keep browser open for a moment so you can see final state
        await asyncio.sleep(3)
        await browser.close()


# Run the script
if __name__ == "__main__":
    asyncio.run(main())