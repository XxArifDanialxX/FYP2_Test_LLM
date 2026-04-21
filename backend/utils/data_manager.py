import json
import os

# This finds the absolute path of your project folder automatically
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(BASE_DIR, 'expert_data.json')

def load_data():
    if not os.path.exists(CONFIG_FILE):
        # If file missing, return empty or default
        return {} 
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)
# ... keep the rest of your save_data function the same

def save_data(data):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(data, f, indent=4)