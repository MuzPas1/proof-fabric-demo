# Terraform — PFP cloud foundation (multi-cloud capable).
# This module provisions the secret store entry for the signing keys and a
# Kubernetes namespace/secret. Cloud-specific resources (EKS/GKE/AKS, DocumentDB/
# Atlas/CosmosDB) are referenced via variables so the same root module targets
# AWS, Azure, or GCP.

terraform {
  required_version = ">= 1.5"
  required_providers {
    kubernetes = { source = "hashicorp/kubernetes", version = ">= 2.23" }
    aws        = { source = "hashicorp/aws", version = ">= 5.0" }
  }
}

variable "cloud"            { type = string  default = "aws" } # aws | gcp | azure
variable "namespace"        { type = string  default = "pfp" }
variable "mongo_url"        { type = string  sensitive = true }
variable "jwt_secret"       { type = string  sensitive = true }
variable "admin_email"      { type = string }
variable "admin_password"   { type = string  sensitive = true }
variable "production_seed"  { type = string  sensitive = true }
variable "demo_seed"        { type = string  sensitive = true }
variable "cors_origins"     { type = string  default = "https://app.pfprotocol.com" }

# --- AWS Secrets Manager entries for the signing keys (KMS_PROVIDER=aws) ---
resource "aws_secretsmanager_secret" "prod_signing" {
  count = var.cloud == "aws" ? 1 : 0
  name  = "pfp/prod/signing"
}
resource "aws_secretsmanager_secret_version" "prod_signing" {
  count         = var.cloud == "aws" ? 1 : 0
  secret_id     = aws_secretsmanager_secret.prod_signing[0].id
  secret_string = var.production_seed
}
resource "aws_secretsmanager_secret" "demo_signing" {
  count = var.cloud == "aws" ? 1 : 0
  name  = "pfp/demo/signing"
}
resource "aws_secretsmanager_secret_version" "demo_signing" {
  count         = var.cloud == "aws" ? 1 : 0
  secret_id     = aws_secretsmanager_secret.demo_signing[0].id
  secret_string = var.demo_seed
}

# --- Kubernetes namespace + app secret ---
resource "kubernetes_namespace" "pfp" {
  metadata { name = var.namespace }
}

resource "kubernetes_secret" "pfp" {
  metadata {
    name      = "pfp-secrets"
    namespace = kubernetes_namespace.pfp.metadata[0].name
  }
  data = {
    MONGO_URL              = var.mongo_url
    JWT_SECRET             = var.jwt_secret
    ADMIN_EMAIL            = var.admin_email
    ADMIN_PASSWORD         = var.admin_password
    AWS_KEY_REF_PRODUCTION = var.cloud == "aws" ? aws_secretsmanager_secret.prod_signing[0].arn : ""
    AWS_KEY_REF_DEMO       = var.cloud == "aws" ? aws_secretsmanager_secret.demo_signing[0].arn : ""
    CORS_ORIGINS           = var.cors_origins
  }
  type = "Opaque"
}

output "namespace" { value = kubernetes_namespace.pfp.metadata[0].name }
