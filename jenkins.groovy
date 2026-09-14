pipeline {
    agent any

    environment {
        DOCKER_HUB_CREDENTIALS = 'DockerHub'
        SOURCE_REPO_URL = 'https://github.com/rdnsx/FileDrop.git'
        DOCKER_IMAGE_NAME = 'rdnsx/filedrop'
        TAG_NAME = 'latest'
        SSH_USER = 'root'
        SSH_HOST = '91.107.199.72'
        SSH_PORT = '22'
        WEBSITE_URL = 'https://drop2share.de'
        WAIT_TIME = 60

        // Must match the USER uid in the Dockerfile.
        APP_UID = '10001'

        NTFY_SERVER = 'https://ntfy.rdnsx.de'
        NTFY_TOPIC = 'RDNSX_Jenkins'
    }

    stages {

        stage('Test') {
            steps {
                sh """
                    docker run --rm -v "\$PWD":/src -w /src python:3.13-slim sh -c '
                        pip install --no-cache-dir -q -r requirements.txt &&
                        python test_app.py'
                """
            }
        }

        stage('Build Docker Image') {
            steps {
                script {
                    def buildNumber = env.BUILD_NUMBER
                    sh "sed -i 's/{{BUILD_NUMBER}}/${buildNumber}/g' templates/index.html"

                    docker.withRegistry('', DOCKER_HUB_CREDENTIALS) {
                        def dockerImage = docker.build("${DOCKER_IMAGE_NAME}:${buildNumber}", ".")
                        dockerImage.push()

                        dockerImage.tag("latest")
                        dockerImage.push("latest")
                    }
                }
            }
        }

        stage('Deploy to Swarm') {
            steps {
                script {
                    sshagent(['Swarm00']) {
                        // Ship the stack file and the cleanup script from this commit
                        // instead of wget-ing them from GitHub: the deploy no longer
                        // depends on the repository staying public, and the cron script
                        // on the cluster can no longer drift away from the repo.
                        sh """
                            ssh -o StrictHostKeyChecking=accept-new -p ${SSH_PORT} ${SSH_USER}@${SSH_HOST} '
                            mount -a &&
                            mkdir -p /mnt/SSS/DockerData/drop2share.de /mnt/SSS/DockerData/scripts &&
                            chown -R ${APP_UID}:${APP_UID} /mnt/SSS/DockerData/drop2share.de &&
                            rm -rf /mnt/SSS/DockerCompose/drop2share.de/ &&
                            mkdir -p /mnt/SSS/DockerCompose/drop2share.de/'

                            scp -o StrictHostKeyChecking=accept-new -P ${SSH_PORT} docker-compose-swarm.yml \
                                ${SSH_USER}@${SSH_HOST}:/mnt/SSS/DockerCompose/drop2share.de/
                            scp -o StrictHostKeyChecking=accept-new -P ${SSH_PORT} delete2share.sh \
                                ${SSH_USER}@${SSH_HOST}:/mnt/SSS/DockerData/scripts/

                            ssh -o StrictHostKeyChecking=accept-new -p ${SSH_PORT} ${SSH_USER}@${SSH_HOST} '
                            chmod +x /mnt/SSS/DockerData/scripts/delete2share.sh &&
                            cd /mnt/SSS/DockerCompose/drop2share.de/ &&
                            docker stack deploy --with-registry-auth -c docker-compose-swarm.yml drop2sharede'
                        """
                    }
                }
            }
        }

        stage('Check Website Status and Notify') {
            steps {
                script {
                    def buildNumber = env.BUILD_NUMBER
                    def ntfyServer = env.NTFY_SERVER
                    def ntfyTopic = env.NTFY_TOPIC
                    def websiteUrl = env.WEBSITE_URL

                    echo "Waiting for ${WAIT_TIME} seconds before checking website status..."
                    sleep time: WAIT_TIME.toInteger(), unit: 'SECONDS'

                    def curlResponse = sh(script: "curl -s -o response.txt -w '%{http_code}' ${websiteUrl}", returnStdout: true).trim()
                    def response = readFile('response.txt').trim()

                    // Match the rendered footer, not a bare number that could appear anywhere.
                    if (curlResponse == '200' && response.contains("Build ${buildNumber}")) {
                        def message = "👍 ${websiteUrl} is successfully running on build ${buildNumber}!"
                        echo message
                        sh "curl -sS -d '${message}' -H 'Actions: view, Check website, ${websiteUrl}' ${ntfyServer}/${ntfyTopic}"
                    } else {
                        def errorMessage = "⛔️ ${websiteUrl} is not responding properly or does not serve build ${buildNumber}!"
                        echo errorMessage
                        sh "curl -sS -d '${errorMessage}' -H 'Actions: view, Check website, ${websiteUrl}' ${ntfyServer}/${ntfyTopic}"
                        error errorMessage
                    }
                }
            }
        }
    }
}
