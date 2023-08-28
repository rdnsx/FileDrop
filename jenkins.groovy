pipeline {
    agent any
    
    environment {
        DOCKER_HUB_CREDENTIALS = 'DockerHub'
        SOURCE_REPO_URL = 'https://github.com/rdnsx/FileDrop.git'
        DOCKER_IMAGE_NAME = 'rdnsx/filedrop'
        SSH_USER = 'root'
        SSH_HOST = '91.107.199.72'
        SSH_PORT = '22'
        WEBSITE_URL = 'https://drop2share.de'
        WAIT_TIME = 30
    }
    
    stages {
        stage('Checkout') {
            steps {
                git branch: 'main', url: env.SOURCE_REPO_URL
            }
        }
        
        stage('Build Docker Image') {
            steps {
                script {
                    def latestTag = "latest"
                    def versionFormat = "1.%d.%d-%d"
                    def currentMajor = 1
                    def currentMinor = 0
                    def currentPatch = 1

                    // Fetch existing tags from Docker Hub
                    def existingTags = sh(script: "docker search ${DOCKER_IMAGE_NAME} | awk '{print \$2}'", returnStdout: true).trim().split('\n')

                    existingTags.each { tag ->
                        if (tag =~ /^(1)\.(\d+)\.(\d+)-\d+$/) {
                            int major = Integer.parseInt(RegExp.$1)
                            int minor = Integer.parseInt(RegExp.$2)
                            int patch = Integer.parseInt(RegExp.$3)
                            if (major == currentMajor && minor == currentMinor && patch >= currentPatch) {
                                currentPatch = patch + 1
                            } else if (major == currentMajor && minor < currentMinor) {
                                currentMinor = minor
                                currentPatch = 1
                            } else if (major > currentMajor) {
                                currentMajor = major
                                currentMinor = 0
                                currentPatch = 1
                            }
                        }
                    }

                    if (currentMinor == 0 && currentPatch > 9) {
                        currentMajor++
                        currentMinor++
                        currentPatch = 0
                    }

                    def customVersionTag = versionFormat.sprintf(currentMajor, currentMinor, currentPatch, env.BUILD_NUMBER)

                    docker.withRegistry('', DOCKER_HUB_CREDENTIALS) {
                        def dockerImageLatest = docker.build("${DOCKER_IMAGE_NAME}:${latestTag}", ".")
                        def dockerImageCustomVersion = docker.build("${DOCKER_IMAGE_NAME}:${customVersionTag}", ".")

                        dockerImageLatest.push()
                        dockerImageCustomVersion.push()
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

        stage('Check Website Status') {
            steps {
                script {

                    echo "Waiting for ${WAIT_TIME} seconds before checking website status..."
                    sleep WAIT_TIME

                    def response = sh(script: "curl -s ${WEBSITE_URL}", returnStdout: true).trim()

                    if (response.contains('File')) {
                        echo "Website is up and contains 'File'."
                    } else {
                        error "Website is not responding properly or does not contain 'File'."
                    }

                }
            }
        }
    }
}
