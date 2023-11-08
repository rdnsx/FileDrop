from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import secrets

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files['file']
    filename = file.filename
    file_extension = os.path.splitext(filename)[1]
    secure_filename = secrets.token_hex(8) + file_extension
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], secure_filename))

    download_link = request.host_url + 'uploads/' + secure_filename

    return jsonify({
        'filename': filename,
        'download_link': download_link
    })

@app.route('/uploads/<filename>')
def download(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/upload', methods=['POST'])
def file_upload():
    uploaded_files = request.files.getlist("file")  # "file" is the name attribute in your input HTML element
    for file in uploaded_files:
        if file:
            # Save each file
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    return 'Files successfully uploaded'


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

