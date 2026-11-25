// Delivery pipeline: runs after merge to main (SCM polling) and nightly (timer).
// A failure stops the pipeline, nothing is deployed. Rollback: kubectl rollout undo deploy/<name> -n idea-validator
// The kubeconfig is a Jenkins credential (id: kubeconfig-test), never in the repository.
pipeline {
  agent any
  triggers {
    pollSCM('H/2 * * * *')   // a GitHub webhook cannot reach Jenkins on a laptop
    cron('H 2 * * *')        // nightly: also runs the full evaluation
  }
  environment {
    REGISTRY = "${env.REGISTRY ?: 'localhost:5000'}"
    NS = 'idea-validator'
    SERVICES = 'gateway orchestrator tools kb scorer verdict agentops'
  }
  stages {
    stage('Checkout') {
      steps {
        checkout scm
        script { env.TAG = sh(returnStdout: true, script: 'git rev-parse --short=7 HEAD').trim() }
      }
    }
    stage('Test') {
      steps { sh 'cd services/verdict && python3 -m unittest && cd ../tools && python3 -m unittest' }
    }
    stage('Build and tag') {
      steps { sh './scripts/build_images.sh "$REGISTRY" "$TAG"' }
    }
    stage('Push') {
      steps { sh './scripts/push_images.sh "$REGISTRY" "$TAG"' }
    }
    stage('Deploy to test cluster') {
      steps {
        withCredentials([file(credentialsId: 'kubeconfig-test', variable: 'KUBECONFIG')]) {
          sh './scripts/deploy.sh "$REGISTRY" "$TAG"'
        }
      }
    }
    stage('Smoke test') {
      steps {
        withCredentials([file(credentialsId: 'kubeconfig-test', variable: 'KUBECONFIG')]) {
          sh './scripts/smoke_test.sh'
        }
      }
    }
    stage('Nightly evaluation') {
      when { triggeredBy 'TimerTrigger' }
      steps {
        withCredentials([file(credentialsId: 'kubeconfig-test', variable: 'KUBECONFIG')]) {
          sh 'kubectl apply -f k8s/eval-job.yaml && ./scripts/check_eval.sh'
        }
      }
    }
  }
  post {
    failure { echo 'Pipeline failed: nothing promoted. Roll back with kubectl rollout undo if a bad release got out.' }
  }
}
