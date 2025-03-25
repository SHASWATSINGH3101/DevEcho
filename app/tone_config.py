import os
import json

AVAILABLE_TONES = [
    "professional",
    "casual",
    "educational",
    "persuasive"
]

def get_current_tone():
    """Get the current tone setting from config file"""
    try:
        # Ensure config directory exists
        os.makedirs('./config', exist_ok=True)
        
        # Try to read existing tone configuration
        with open('./config/tone.json', 'r', encoding='utf-8') as tone_file:
            tone_data = json.load(tone_file)
            tone = tone_data.get("tone", "professional")
            
            # Validate that tone is in available tones
            if tone not in AVAILABLE_TONES:
                tone = "professional"
                
            return tone
    except (FileNotFoundError, json.JSONDecodeError):
        # Create the tone.json file with default tone
        set_tone("professional")
        return "professional"

def set_tone(tone):
    """Set a new tone in the config file"""
    if tone not in AVAILABLE_TONES:
        raise ValueError(f"Tone must be one of: {', '.join(AVAILABLE_TONES)}")
        
    # Ensure config directory exists
    os.makedirs('./config', exist_ok=True)
    
    # Write the new tone setting
    with open('./config/tone.json', 'w', encoding='utf-8') as tone_file:
        json.dump({"tone": tone}, tone_file, indent=4)
    
    return tone

def list_available_tones():
    """Return a list of all available tones"""
    return AVAILABLE_TONES

if __name__ == "__main__":
    # Command line interface for testing
    import sys
    
    if len(sys.argv) < 2:
        current_tone = get_current_tone()
        print(f"Current tone: {current_tone}")
        print(f"Available tones: {', '.join(AVAILABLE_TONES)}")
        print("Usage: python tone_config.py [tone_name]")
    else:
        tone = sys.argv[1]
        try:
            set_tone(tone)
            print(f"Tone set to: {tone}")
        except ValueError as e:
            print(f"Error: {e}")
            print(f"Available tones: {', '.join(AVAILABLE_TONES)}")