"""Configuration module for loading API keys and settings."""

import json
import os

# Get the project root directory (one level up from services folder)
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_current_dir)
_config_path = os.path.join(_project_root, 'config.json')

# Load your API key from config.json
with open(_config_path) as config_file:
    config = json.load(config_file)

API_KEY = config['API_KEY']
