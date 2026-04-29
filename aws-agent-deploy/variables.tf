variable "instance_name" {
  description = "Value of the EC2 instance's Name tag."
  type        = string
  default     = "My-First-Terraform-EC2"
}

variable "instance_type" {
  description = "The EC2 instance's type."
  type        = string
  default     = "t3.micro"
}

variable "allowed_http_cidr" {
  description = "CIDR block allowed to access HTTP port 80."
  type        = string
  default     = "0.0.0.0/0"
}

variable "agent_api_key" {
  description = "API key configured for the deployed agent."
  type        = string
  default     = "dev-key-change-me-in-production"
  sensitive   = true
}

variable "app_repository_url" {
  description = "Optional Git repository URL to clone and run with docker compose. Empty value deploys a built-in feasibility health service."
  type        = string
  default     = ""
}

variable "app_repository_ref" {
  description = "Optional branch, tag, or commit to checkout after cloning app_repository_url."
  type        = string
  default     = ""
}

variable "tags" {
  description = "Common tags applied to AWS resources."
  type        = map(string)
  default = {
    Project     = "agent-deployment"
    Environment = "test"
    ManagedBy   = "terraform"
  }
}
