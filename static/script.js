document.addEventListener('DOMContentLoaded', () => {
    const dropArea = document.getElementById('dropArea');
    const fileInput = document.getElementById('fileInput');
    const uploadProgress = document.getElementById('uploadProgress');
    const progressBar = document.getElementById('progressBar');
    const progressLabel = document.getElementById('progressLabel');
    const errorMessage = document.getElementById('errorMessage');
    const results = document.getElementById('results');
    const resultTemplate = document.getElementById('resultTemplate');

    let busy = false;

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(name => {
        dropArea.addEventListener(name, preventDefaults);
        document.body.addEventListener(name, preventDefaults);
    });
    ['dragenter', 'dragover'].forEach(name =>
        dropArea.addEventListener(name, () => dropArea.classList.add('highlight'))
    );
    ['dragleave', 'drop'].forEach(name =>
        dropArea.addEventListener(name, () => dropArea.classList.remove('highlight'))
    );

    dropArea.addEventListener('drop', event => handleFiles(event.dataTransfer.files));
    dropArea.addEventListener('click', () => fileInput.click());
    dropArea.addEventListener('keydown', event => {
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            fileInput.click();
        }
    });
    fileInput.addEventListener('change', () => handleFiles(fileInput.files));

    function preventDefaults(event) {
        event.preventDefault();
        event.stopPropagation();
    }

    function showError(text) {
        errorMessage.textContent = text;
        errorMessage.hidden = false;
    }

    async function handleFiles(fileList) {
        const files = Array.from(fileList || []);
        fileInput.value = '';
        if (!files.length || busy) {
            return;
        }

        busy = true;
        errorMessage.hidden = true;
        uploadProgress.hidden = false;

        for (let i = 0; i < files.length; i += 1) {
            const file = files[i];
            const position = files.length > 1 ? `(${i + 1}/${files.length}) ` : '';
            progressBar.style.width = '0%';
            progressLabel.textContent = `${position}Uploading ${file.name}…`;
            try {
                addResult(await uploadFile(file, percent => {
                    progressBar.style.width = `${percent}%`;
                }));
            } catch (error) {
                showError(`${file.name}: ${error.message}`);
                break;
            }
        }

        uploadProgress.hidden = true;
        progressLabel.textContent = '';
        busy = false;
    }

    function uploadFile(file, onProgress) {
        return new Promise((resolve, reject) => {
            const formData = new FormData();
            formData.append('file', file);

            const xhr = new XMLHttpRequest();
            xhr.open('POST', '/upload', true);
            xhr.responseType = 'json';

            xhr.upload.addEventListener('progress', event => {
                if (event.lengthComputable) {
                    onProgress((event.loaded / event.total) * 100);
                }
            });

            xhr.addEventListener('load', () => {
                const body = xhr.response;
                if (xhr.status === 200 && body && body.download_link) {
                    resolve(body);
                } else if (xhr.status === 413) {
                    reject(new Error('File is too large.'));
                } else if (xhr.status === 429) {
                    reject(new Error('Too many uploads. Please try again later.'));
                } else {
                    reject(new Error((body && body.message) || `Upload failed (HTTP ${xhr.status}).`));
                }
            });
            xhr.addEventListener('error', () => reject(new Error('Network error during upload.')));
            xhr.addEventListener('abort', () => reject(new Error('Upload was cancelled.')));

            xhr.send(formData);
        });
    }

    function addResult(response) {
        const node = resultTemplate.content.cloneNode(true);
        const link = node.querySelector('.result-url');
        const copyButton = node.querySelector('.copy-button');

        node.querySelector('.result-name').textContent = response.filename;
        link.href = response.download_link;
        link.textContent = response.download_link;
        node.querySelector('.result-expiry').textContent =
            `Deleted automatically after ${response.expires_in_hours} hours.`;

        copyButton.addEventListener('click', async () => {
            try {
                await navigator.clipboard.writeText(response.download_link);
                copyButton.textContent = 'Copied';
            } catch (error) {
                copyButton.textContent = 'Copy failed';
            }
            setTimeout(() => { copyButton.textContent = 'Copy'; }, 2000);
        });

        results.prepend(node);
    }
});
