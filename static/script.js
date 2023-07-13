document.addEventListener('DOMContentLoaded', () => {
    const dropArea = document.getElementById('dropArea');
    const fileInput = document.getElementById('fileInput');
    const uploadProgress = document.getElementById('uploadProgress');
    const progressBar = document.querySelector('.progress-bar');
    const uploadSuccess = document.getElementById('uploadSuccess');
    const fileName = document.getElementById('fileName');
    const downloadLink = document.getElementById('downloadLink');

    // Prevent default drag behaviors
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, preventDefaults, false);
        document.body.addEventListener(eventName, preventDefaults, false);
    });

    // Highlight drop area when item is dragged over it
    ['dragenter', 'dragover'].forEach(eventName => {
        dropArea.addEventListener(eventName, highlight, false);
    });

    // Unhighlight drop area when item is dragged out of it
    ['dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, unhighlight, false);
    });

    // Handle dropped files
    dropArea.addEventListener('drop', handleDrop, false);

    // Open file input when drop area is clicked
    dropArea.addEventListener('click', () => {
        fileInput.click();
    });

    // Handle file selection
    fileInput.addEventListener('change', handleFiles, false);

    // Prevent default drag behaviors
    function preventDefaults(event) {
        event.preventDefault();
        event.stopPropagation();
    }

    // Highlight drop area
    function highlight() {
        dropArea.classList.add('highlight');
    }

    // Unhighlight drop area
    function unhighlight() {
        dropArea.classList.remove('highlight');
    }

    // Handle dropped files
    function handleDrop(event) {
        const files = event.dataTransfer.files;
        fileInput.files = files;
        handleFiles(files);
    }

    // Handle selected files
    function handleFiles(files) {
        if (files.length > 0) {
            uploadFile(files[0]);
        }
    }

    // Upload file
    function uploadFile(file) {
        const url = '/upload';
        const formData = new FormData();
        formData.append('file', file);

        const xhr = new XMLHttpRequest();
        xhr.open('POST', url, true);

        xhr.upload.addEventListener('progress', e => {
            const progress = (e.loaded / e.total) * 100;
            progressBar.style.width = `${progress}%`;
        });

        xhr.addEventListener('load', () => {
            if (xhr.status === 200) {
                const response = JSON.parse(xhr.responseText);
                showUploadSuccess(response);
            } else {
                console.error('Upload error');
            }
        });

        xhr.addEventListener('error', () => {
            console.error('Upload error');
        });

        xhr.addEventListener('abort', () => {
            console.log('Upload aborted');
        });

        xhr.send(formData);
    }

    // Show upload success message
    function showUploadSuccess(response) {
        fileName.textContent = response.filename;
        downloadLink.href = response.download_link;
        downloadLink.textContent = response.download_link;
        
        uploadProgress.classList.add('hidden');
        uploadSuccess.classList.remove('hidden');
    }
});
