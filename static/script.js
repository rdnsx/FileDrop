document.addEventListener('DOMContentLoaded', () => {
    const dropArea = document.getElementById('dropArea');
    const fileInput = document.getElementById('fileInput');
    const uploadProgress = document.getElementById('uploadProgress');
    const progressBar = document.getElementById('progressBar');
    const progressLabel = document.getElementById('progressLabel');
    const errorMessage = document.getElementById('errorMessage');
    const results = document.getElementById('results');
    const resultTemplate = document.getElementById('resultTemplate');
    const batchResult = document.getElementById('batchResult');
    const batchTitle = document.getElementById('batchTitle');
    const batchUrl = document.getElementById('batchUrl');
    const batchCopy = document.getElementById('batchCopy');
    const batchExpiry = document.getElementById('batchExpiry');

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
        batchResult.hidden = true;
        uploadProgress.hidden = false;

        const uploaded = [];
        for (let i = 0; i < files.length; i += 1) {
            const file = files[i];
            const position = files.length > 1 ? `(${i + 1}/${files.length}) ` : '';
            progressBar.style.width = '0%';
            progressLabel.textContent = `${position}Uploading ${file.name}…`;
            try {
                const response = await uploadFile(file, percent => {
                    progressBar.style.width = `${percent}%`;
                });
                addResult(response);
                uploaded.push(response);
            } catch (error) {
                showError(`${file.name}: ${error.message}`);
                break;
            }
        }

        if (uploaded.length > 1) {
            progressLabel.textContent = 'Preparing the archive link…';
            await showBatchLink(uploaded);
        }

        uploadProgress.hidden = true;
        progressLabel.textContent = '';
        busy = false;
    }

    // One shareable link for everything that was just uploaded.
    async function showBatchLink(uploaded) {
        try {
            const response = await fetch('/batch', {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
                body: JSON.stringify({
                    files: uploaded.map(item => ({id: item.id, name: item.filename})),
                }),
            });
            const body = await response.json();
            if (!response.ok || !body.zip_link) {
                throw new Error(body.message || `HTTP ${response.status}`);
            }
            batchTitle.textContent = `All ${body.file_count} files as one archive`;
            batchUrl.href = body.zip_link;
            batchUrl.textContent = body.zip_link;
            batchExpiry.textContent = `Deleted automatically after ${body.expires_in_hours} hours.`;
            wireCopy(batchCopy, body.zip_link);
            batchResult.hidden = false;
        } catch (error) {
            // The individual links above still work, so this is not fatal.
            showError(`Archive link unavailable: ${error.message}`);
        }
    }

    function wireCopy(button, text) {
        button.onclick = async () => {
            try {
                await navigator.clipboard.writeText(text);
                button.textContent = 'Copied';
            } catch (error) {
                button.textContent = 'Copy failed';
            }
            setTimeout(() => { button.textContent = 'Copy'; }, 2000);
        };
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

        wireCopy(copyButton, response.download_link);

        results.prepend(node);
    }
});
