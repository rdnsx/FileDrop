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
        // Assuming 'files' is an array of file objects
        for (let i = 0; i < files.length; i++) {
          uploadFile(files[i]);
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

    function updateProgress(file, progress) {
        // Find the progress bar element for the file, assuming there is one for each file
        const progressBar = document.getElementById('progress-bar-' + file.name);
        if (progressBar) {
          progressBar.style.width = progress + '%';
        }
      }
      
      // You would call this function in the onprogress event of the XMLHttpRequest
      xhr.upload.onprogress = function(event) {
        if (event.lengthComputable) {
          const progress = (event.loaded / event.total) * 100;
          updateProgress(file, progress);
        }
      };      

    // Show upload success message
    function showUploadSuccess(response) {
        fileName.textContent = response.filename;
        downloadLink.href = response.download_link;
        downloadLink.textContent = response.download_link;
        
        uploadProgress.classList.add('hidden');
        uploadSuccess.classList.remove('hidden');
    }
});
