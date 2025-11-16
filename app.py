from flask import Flask, jsonify, send_from_directory, send_file, request
from werkzeug.utils import secure_filename
import csv
import ast
import json
import os
import sys
import tempfile
import uuid

# Increase CSV field size limit to handle large conversation fields
csv.field_size_limit(sys.maxsize)

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()

# Store uploaded CSV data in memory (session_id -> file path)
uploaded_files = {}

def extract_user_prompt(conv_str):
    """Extract the user prompt from conversation_a or conversation_b (not full_conversation)"""
    if not conv_str:
        return ''
    
    import re
    
    try:
        # Extract user prompt from conversation_a/b (these have the actual prompt for this turn)
        # The text can be quoted (with escaped quotes) or unquoted
        # First try quoted text with escaped quotes: 'text': 'content with \'escaped quotes\''
        # Pattern handles: 'text': '...' where ... may contain \' or \\
        user_pattern_quoted = r"'role':\s*['\"]?user['\"]?[^}]*'text':\s*'((?:[^'\\]|\\.)*)'"
        user_match = re.search(user_pattern_quoted, conv_str, re.DOTALL)
        if user_match:
            text = user_match.group(1)
            # Unescape the text
            text = text.replace("\\'", "'").replace("\\\\", "\\")
            return text
        
        # Try unquoted text - it ends at comma followed by 'image' or 'num_tokens' or closing bracket
        # Pattern: 'text': text_content, 'image' or 'text': text_content} or 'text': text_content]
        user_pattern_unquoted = r"'role':\s*['\"]?user['\"]?[^}]*'text':\s*([^,}]+?)(?=\s*,\s*['\"]image['\"]|\s*,\s*['\"]num_tokens['\"]|\s*[}\]])"
        user_match2 = re.search(user_pattern_unquoted, conv_str, re.DOTALL)
        if user_match2:
            text = user_match2.group(1).strip()
            return text
        
        return ''
    except Exception as e:
        return ''

def extract_assistant_response(conv_str):
    """Extract assistant response text from conversation - handles quoted strings with escaped quotes"""
    if not conv_str:
        return ''
    
    import re
    
    try:
        # Find the assistant role section
        assistant_match = re.search(r"'role':\s*['\"]?assistant['\"]?\s*,\s*'content':\s*\[([^\]]+)\]", conv_str, re.DOTALL)
        if not assistant_match:
            # Try alternative pattern
            assistant_match = re.search(r"'role':\s*assistant[^}]*'content':\s*\[([^\]]+)\]", conv_str, re.DOTALL)
        
        if assistant_match:
            content_str = assistant_match.group(1)
            # Now find the text field within this content
            # Look for 'text': '...' where we need to handle the closing quote properly
            # The text is quoted, so we need to find the matching closing quote
            text_field_match = re.search(r"'text':\s*'", content_str)
            if text_field_match:
                # Find the position after the opening quote
                start_pos = text_field_match.end()
                # Now find the matching closing quote (not escaped)
                remaining = content_str[start_pos:]
                # Look for closing quote followed by comma, }, or ]
                # Handle escaped quotes: \' should not count as closing quote
                quote_pattern = r"(?<!\\)'(?=\s*[,}\]])"
                end_match = re.search(quote_pattern, remaining)
                if end_match:
                    text = remaining[:end_match.start()]
                    # Unescape any escaped quotes
                    text = text.replace("\\'", "'")
                    return text
        
        # Fallback: simpler pattern for quoted text (may miss some edge cases)
        pattern_quoted = r"'role':\s*['\"]?assistant['\"]?[^}]*'text':\s*'((?:[^'\\]|\\.)*)'"
        matches = re.findall(pattern_quoted, conv_str, re.DOTALL)
        if matches:
            # Unescape the text
            text = matches[-1].replace("\\'", "'").replace("\\\\", "\\")
            return text
        
        # Last resort: try to extract between quotes more carefully
        # Find 'text': ' and then find the next unescaped quote
        text_start_pattern = r"'text':\s*'"
        start_match = re.search(text_start_pattern, conv_str)
        if start_match:
            # Find all occurrences and get the last one (assistant response)
            all_matches = list(re.finditer(text_start_pattern, conv_str))
            if all_matches:
                last_match = all_matches[-1]
                start_pos = last_match.end()
                # Find closing quote that's not escaped
                remaining = conv_str[start_pos:]
                # Look for quote followed by comma or closing bracket
                end_match = re.search(r"(?<!\\)'(?=\s*[,}\]])", remaining)
                if end_match:
                    text = remaining[:end_match.start()]
                    text = text.replace("\\'", "'").replace("\\\\", "\\")
                    return text
        
        return ''
    except Exception as e:
        return ''

def parse_conversations_from_csv(csv_path, session_id=None):
    """Parse conversations from CSV file, optionally filtered by session_id"""
    conversations = []
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Filter by session_id if provided
                if session_id and row.get('evaluation_session_id') != session_id:
                    continue
                
                # Extract user prompt from conversation_a (it has the actual prompt for this turn)
                # conversation_a and conversation_b should have the same user prompt
                user_prompt = extract_user_prompt(row.get('conversation_a', ''))
                response_a = extract_assistant_response(row.get('conversation_a', ''))
                response_b = extract_assistant_response(row.get('conversation_b', ''))
                
                conversation = {
                    'id': row.get('id', ''),
                    'user_prompt': user_prompt,
                    'model_a': row.get('model_a', ''),
                    'model_b': row.get('model_b', ''),
                    'response_a': response_a,
                    'response_b': response_b,
                    'winner': row.get('winner', ''),
                    'timestamp': row.get('timestamp', ''),
                    'evaluation_order': row.get('evaluation_order', '')
                }
                conversations.append(conversation)
    except Exception as e:
        raise Exception(f"Error parsing CSV: {str(e)}")
    
    # Sort by evaluation_order to ensure correct conversation sequence
    # Handle both numeric and string values
    try:
        conversations.sort(key=lambda x: int(x['evaluation_order']) if x['evaluation_order'] and x['evaluation_order'].isdigit() else float('inf'))
    except (ValueError, TypeError):
        # If sorting fails, keep original order
        pass
    
    return conversations

@app.route('/api/conversations')
def get_conversations():
    """Read default CSV and return formatted conversation data"""
    csv_path = os.path.join(os.path.dirname(__file__), 'session-records-sorted.csv')
    
    try:
        conversations = parse_conversations_from_csv(csv_path)
        return jsonify(conversations)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/upload', methods=['POST'])
def upload_csv():
    """Upload CSV file and return unique session IDs"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not file.filename.endswith('.csv'):
        return jsonify({'error': 'File must be a CSV'}), 400
    
    try:
        # Save uploaded file temporarily
        file_id = str(uuid.uuid4())
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{file_id}_{filename}")
        file.save(file_path)
        
        # Parse CSV to get session IDs
        session_ids = set()
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    session_id = row.get('evaluation_session_id', '')
                    if session_id:
                        session_ids.add(session_id)
        except Exception as e:
            # Clean up file on error
            if os.path.exists(file_path):
                os.remove(file_path)
            return jsonify({'error': f'Invalid CSV format: {str(e)}'}), 400
        
        # Store file path for later use
        uploaded_files[file_id] = file_path
        
        session_ids_list = sorted(list(session_ids))
        
        return jsonify({
            'file_id': file_id,
            'session_ids': session_ids_list,
            'count': len(session_ids_list)
        })
    except Exception as e:
        return jsonify({'error': f'Error processing file: {str(e)}'}), 500

@app.route('/api/conversations/<file_id>')
def get_conversations_from_upload(file_id):
    """Get conversations from uploaded file, optionally filtered by session_id"""
    session_id = request.args.get('session_id', None)
    
    if file_id not in uploaded_files:
        return jsonify({'error': 'File not found'}), 404
    
    file_path = uploaded_files[file_id]
    
    if not os.path.exists(file_path):
        return jsonify({'error': 'File no longer available'}), 404
    
    try:
        conversations = parse_conversations_from_csv(file_path, session_id)
        return jsonify(conversations)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/')
def index():
    """Serve the main HTML page"""
    return send_file(os.path.join('static', 'index.html'))

@app.route('/static/<path:filename>')
def static_files(filename):
    """Serve static files (CSS, JS)"""
    return send_from_directory('static', filename)

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)

