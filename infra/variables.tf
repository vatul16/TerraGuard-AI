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
  description = "Docker image for the ECS task"
  type        = string
  default     = "nginx:alpine"
}

variable "app_port" {
  description = "Port the application listens on"
  type        = number
  default     = 80
}
