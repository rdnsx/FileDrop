# FileDrop

This is a simple web application built using Flask that allows users to upload files to the server. The uploaded files are stored in a secure manner, and users are provided with a download link to access their uploaded files.

## Features

- Drag and drop file upload support
- Upload progress tracking
- Secure filename generation
- Download link for uploaded files

## Prerequisites

Before running this application, ensure you have the following installed:

- Python 3.x
- Flask

## Installation

1. Clone the repository to your local machine:

```bash
git clone https://github.com/your-username/file-upload-app.git
cd file-upload-app
```

2. Create a virtual environment (optional but recommended):

```bash
python -m venv venv
source venv/bin/activate    # On Windows: venv\Scripts\activate
```

3. Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Usage

1. Run the Flask application:

```bash
python app.py
```

2. Open your web browser and navigate to `http://localhost:5000/`.

3. Drag and drop a file onto the drop area or click on the drop area to select a file using the file input.

4. The upload progress will be displayed, and once the file is uploaded successfully, you will see a success message with the filename and a download link.

## Configuration

By default, the uploaded files are stored in the `uploads/` folder within the application directory. You can change this by modifying the `UPLOAD_FOLDER` variable in `app.py`:

```python
app.config['UPLOAD_FOLDER'] = 'your_custom_upload_folder/'
```

## Notes

- This application is intended for educational purposes and may not be suitable for production environments without further security considerations.

- Ensure that the server has sufficient permissions to write to the `UPLOAD_FOLDER` directory.

# Usage with Docker

docker pull rdnsx/filedrop

docker run -d -p 3266:5000 -v /path/to/local/filedrop/:/app/uploads --name FileDrop rdnsx/filedrop 

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Acknowledgments

- This application was built using Flask, a micro web framework for Python.

- The front-end drag-and-drop functionality was inspired by various online tutorials and examples.

## Contributing

Contributions are welcome! If you find any issues or have suggestions for improvements, feel free to open an issue or submit a pull request.

Thank you for using this file upload web application! If you have any questions or need further assistance, please don't hesitate to contact us.

Happy uploading!
