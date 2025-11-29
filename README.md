# TripRip: TripIt Flight Exporter

<aside>

A Python script that automatically extracts all your flight history from TripIt and exports it to CSV format using browser automation and AI.

- Minimal cost (~$0.15 per 100 trips)
- Minimal time (~10 minutes for 100 trips, compared to hours manually copying and pasting your full flight history)
- Beginner-friendly (Runs in visible browser so you can see what it's doing; easy to spot-check data against TripIt)
- Safe (Credentials never stored, just typed into the browser)
</aside>

## What This Does

This script:

1. Opens **TripIt** in an automated browser
2. Navigates through all your past trips on the TripIt website
Uses a Python library called **Playwright** that opens/controls a Chrome window automatically on your behalf
3. Uses **Anthropic Claude** for AI-powered data extraction of flight details from each trip page
Uses **Haiku**, Claude’s fastest/cheapest model via the **Claude API**
4. Exports everything to a CSV file compatible with OpenFlights

## Prerequisites

Before you start, you'll need:

1. **Basic terminal/command line familiarity** (you'll run a few commands)
2. **Python** installed on your computer
3. **TripIt account** with flight history to export
4. **Anthropic API key (**sign up for a developer account at [https://platform.claude.com](https://platform.claude.com/))
    1. Note: You’ll need to buy some credits. The cost of running this script is only about $0.15 per 100 trips using Claude's cheapest model (Haiku), but I believe $5 is the minimum purchase.

## Quick Start Guide

<aside>

### 🤓 Vibe coding for the first time?

Copy and paste this into any LLM (Claude, ChatGPT, etc.), attaching the script and quick start guide, to get help.

```xml
I'm trying to use a Python script that exports flight history from TripIt. I have two documents:

1. The Python script (triprip.py)
2. The quick start guide

Here's where I'm stuck: [setup, installation, running the script, etc.]

Here's what I see in the terminal:
[PASTE ANY ERROR MESSAGES HERE]

My setup:
- Operating System: [Mac/Windows/Linux]

Can you help me understand what's wrong and what I should do next? Please explain in simple terms - I'm not very technical / experienced with coding.
```

</aside>

### 1. Download Files

1. Create a folder called `triprip_export` for this project
2. Download these files into that folder:
    - `triprip.py` - the Python script
    - `requirements.txt` - the dependencies file, which should contain:
        
        ```xml
        playwright==1.48.0
        anthropic==0.39.0
        ```
        

### 2. Get Your Claude API Key

1. Go to [https://console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys)
2. Sign up or log in
3. Create a new API key
4. Copy it and save it somewhere for Step 3 (it probably starts with `sk-ant-...`)
5. Purchase some credits at [https://platform.claude.com/settings/billing](https://platform.claude.com/settings/billing) (you’ll only need about $0.15 per 100 trips, but you’ll probably need to round up to the minimum purchase threshold ~$5)

### 3. Configure the Script

1. Open `triprip.py` in a text editor
2. Find the line `CLAUDE_API_KEY = "your-api-key-here"`
3. Replace `"your-api-key-here"` with your actual API key from Step 2
4. Save the file

### 4. Set Up Python Environment

Open terminal/command prompt, navigate to your `triprip_export` folder, and set up Python dependencies:

**Mac/Linux:**

```bash
cd triprip_export
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

**Windows:**

```bash
cd triprip_export
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

### 5. Run It

**Mac/Linux:**

```bash
python3 triprip.py
```

**Windows:**

```bash
python triprip.py
```

**What happens:**

1. Browser opens to TripIt
2. You log in manually
3. Press Enter in terminal when you see your past trips
4. Script runs automatically (takes ~10 minutes for 100 trips)
5. Table prints in terminal so you can spot-check it against your TripIt data
6. CSV file saved as `flights_export.csv`

## Output Format

The CSV uses OpenFlights schema with these columns populated:

- **Date**: Flight date (YYYY-MM-DD)
- **From**: Origin airport (IATA code)
- **To**: Destination airport (IATA code)
- **Flight_Number**: Airline code + number (e.g., "UA794")

Other OpenFlights columns (Airline, Distance, Seat, Class, etc.) are intentionally left blank. OpenFlights should populate Airline and Distance automatically based on the other 4 populated fields. You can fill in the rest manually if desired.

<aside>

## 🤓 Tips

- **First run**: Start with just watching it process 10-20 trips to verify accuracy
- **Leave it running**: Don't close the browser or interact with it while it's working
- **Spot check:** Use the table printed in terminal to verify a few random flights against TripIt
- **Re-runs**: Safe to run multiple times; it always processes all trips from scratch
- **Errors**: If individual trips fail, they're skipped with an error message (check terminal output)
</aside>