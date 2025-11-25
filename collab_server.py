import os
import uuid
import json
import eventlet
import socketio
from flask import Flask, request, jsonify, send_from_directory


# Socket.IO + Flask app (uses eventlet)
sio = socketio.Server(cors_allowed_origins='*')
app = Flask(__name__)
app.wsgi_app = socketio.WSGIApp(sio, app.wsgi_app)

# Simple canonical in-memory state
CANV_STATE = {
    'strokes': [],
    'attachments': [],
    'texts': []
}

# ensure uploads folder
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.route('/upload', methods=['POST'])
def upload_file():
    """Accept a file upload (form field 'file') and save it to ./uploads.
    Returns: JSON {url, name} with a relative URL under the server.
    """
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'no file'}), 400
        f = request.files['file']
        name = f.filename or 'upload'
        ext = os.path.splitext(name)[1] or '.png'
        fname = f'{uuid.uuid4().hex}{ext}'
        dest = os.path.join(UPLOAD_DIR, fname)
        f.save(dest)
        url = f'/uploads/{fname}'
        CANV_STATE['attachments'].append({'url': url, 'name': fname})
        print('Uploaded file saved:', dest, '->', url)
        return jsonify({'url': url, 'name': fname}), 201
    except Exception as e:
        print('Upload error:', e)
        return jsonify({'error': str(e)}), 500


@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(UPLOAD_DIR, filename)


@sio.event
def connect(sid, environ):
    print('Client connected:', sid)
    # send current state to new client
    sio.emit('init_state', CANV_STATE, room=sid)


@sio.event
def disconnect(sid):
    print('Client disconnected:', sid)


@sio.on('operation')
def on_operation(sid, data):
    try:
        t = data.get('type')
        payload = data.get('payload', {})
        if t == 'stroke':
            CANV_STATE['strokes'].append(payload)
        elif t == 'attach':
            CANV_STATE['attachments'].append(payload)
        elif t == 'text':
            CANV_STATE['texts'].append(payload)
        # broadcast to others
        sio.emit('operation', data, skip_sid=sid)
    except Exception as e:
        print('Error handling operation:', e)


@app.route('/health')
def health():
    return 'OK', 200


if __name__ == '__main__':
    print('Starting collab server on 0.0.0.0:5001')
    eventlet.wsgi.server(eventlet.listen(('0.0.0.0', 5001)), app)
