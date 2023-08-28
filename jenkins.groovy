pipeline {
    agent any
    
    environment {
        DOCKER_HUB_CREDENTIALS = 'DockerHub'
        SOURCE_REPO_URL = 'https://github.com/rdnsx/FileDrop.git'
        DOCKER_IMAGE_NAME = 'rdnsx/filedrop'
        LATEST_TAG = 'latest'
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

        stage('Get Latest Tag') {
            steps {
                script {
                    def dockerHubUrl = "https://hub.docker.com/v2/repositories/${DOCKER_IMAGE_NAME}/tags/?page_size=100"
                    def response = sh(script: "curl -s ${dockerHubUrl}", returnStdout: true)
                    def latestTag = findLatestTag(response)
                    echo "Latest Docker tag found: ${latestTag}"
                    env.TAG_NAME = incrementTag(latestTag)
                }
            }
        }
        
        stage('Build Docker Image') {
            steps {
                script {
                    docker.withRegistry('', DOCKER_HUB_CREDENTIALS) {
                        def dockerImage = docker.build("${DOCKER_IMAGE_NAME}:${TAG_NAME}", ".")
                        dockerImage.push()

                        dockerImage.tag("${LATEST_TAG}")
                        dockerImage.push("${LATEST_TAG}")
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

def findLatestTag(response) {
    def jsonSlurper = new groovy.json.JsonSlurper()
    def tags = jsonSlurper.parseText(response).results.name
    def numericTags = tags.findAll { tag -> tag.matches("\\d+(\\.\\d+)*") }
    def sortedTags = numericTags.sort { a, b ->
        a.split('.').collect { it.toInteger() } <=> b.split('.').collect { it.toInteger() }
    }
    return sortedTags.last()
}

def incrementTag(tag) {
    def parts = tag.tokenize('.')
    def lastPart = parts[-1] as Integer
    lastPart++
    parts[-1] = lastPart.toString()
    return parts.join('.')
}