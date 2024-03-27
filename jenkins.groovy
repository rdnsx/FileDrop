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

        NTFY_SERVER = 'ntfy.rdnsx.de'
        NTFY_TOPIC = 'RDNSX_Jenkins'
    }
    
    stages {
        
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
                        sh """
                            ssh -o StrictHostKeyChecking=no -p ${SSH_PORT} ${SSH_USER}@${SSH_HOST} '
                            mount -a &&
                            cd /mnt/SSS/DockerData/ &&
                            if [ ! -d "drop2share.de/" ]; then
                                mkdir drop2share.de/
                            fi &&
                            cd /mnt/SSS/DockerCompose/ &&
                            rm -rf drop2share.de/ &&
                            mkdir drop2share.de/ &&
                            cd drop2share.de/ &&
                            wget https://raw.githubusercontent.com/rdnsx/FileDrop/main/docker-compose-swarm.yml &&
                            docker stack deploy -c docker-compose-swarm.yml drop2sharede;'
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

                    if (curlResponse == '200' && response.contains(buildNumber)) {
                        def message = "👍 ${websiteUrl} is successfully running on build ${buildNumber}!"
                        echo message
                        sh "curl -d '${message}' -H 'Actions: view, Check website, ${websiteUrl}' ${ntfyServer}/${ntfyTopic}"
                    } else {
                        def errorMessage = "⛔️ ${websiteUrl} is not responding properly or does not contain ${buildNumber}!"
                        echo errorMessage
                        sh "curl -d '${errorMessage}' -H 'Actions: view, Check website, ${websiteUrl}' ${ntfyServer}/${ntfyTopic}"
                        error errorMessage
                    }
                }
            }
        }
    }
}