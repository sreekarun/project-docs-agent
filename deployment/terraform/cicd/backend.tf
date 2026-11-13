terraform {
  backend "gcs" {
    bucket = "adk-chatbot-prod-terraform-state"
    prefix = "project-docs-agent/prod"
  }
}
