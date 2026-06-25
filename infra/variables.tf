variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "ap-south-1"
}

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "terraguard"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

variable "db_password" {
  description = "RDS master password"
  type        = string
  sensitive   = true
}

variable "app_image" {
  description = "Docker image URI for the ECS task. Left empty on first deploy; CI/CD sets this."
  type        = string
  default     = ""
}

variable "app_port" {
  description = "Port the application listens on"
  type        = number
  default     = 3000
}

variable "bastion_key_name" {
  description = "Name of key pair used for Bastion Host"
  type        = string
}

variable "github_org" {
  description = "Your GitHub username or org name (used in OIDC trust policy)"
  type        = string
}

variable "github_repo" {
  description = "Your GitHub repository name (used in OIDC trust policy)"
  type        = string
}
