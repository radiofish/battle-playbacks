# Battle Playbacks

A web application that visualizes AI model battle conversations from CSV data, mimicking the battle arena interface.

## Setup

1. Install dependencies:
```bash
pip3 install -r requirements.txt
```

2. Run the Flask server:
```bash
python3 app.py
```

3. Open your browser and navigate to:
```
http://localhost:5000
```

## Features

- Upload CSV files with conversation data
- Displays user prompts and model responses side-by-side
- Highlights winners (green) and ties (gray)
- Handles multiple evaluation sessions with session selection
- Automatically sorts conversations by `evaluation_order`
- Scrollable response panels with expand/collapse functionality
- Clean, chat-like interface similar to battle arenas

## CSV Format

The application expects CSV files with the following columns:
- `evaluation_session_id` - Session identifier
- `evaluation_order` - Order of conversation in the session
- `model_a`, `model_b` - Model names
- `winner` - Winner: `model_a`, `model_b`, or `tie`
- `conversation_a`, `conversation_b` - Conversation data (JSON-like format)
- `full_conversation` - Full conversation history

For a sample dataset please visit: https://huggingface.co/datasets/lmarena-ai/arena-human-preference-140k/

## File Structure

- `app.py` - Flask backend server
- `static/index.html` - Main HTML page
- `static/style.css` - Styling
- `static/script.js` - Frontend JavaScript
- `requirements.txt` - Python dependencies

