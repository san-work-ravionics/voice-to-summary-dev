# ── AWS Connection ────────────────────────────────────────────────────────────

variable "aws_region" {
  description = "AWS region — must match RITA's region"
  type        = string
  default     = "ap-south-1"
}

# ── Networking ────────────────────────────────────────────────────────────────

variable "vts_subnet_cidr" {
  description = "CIDR for VtS subnet in RITA's VPC (10.0.1.0/24 is RITA's)"
  type        = string
  default     = "10.0.2.0/24"
}

# ── EC2 Configuration ─────────────────────────────────────────────────────────

variable "instance_type" {
  description = "EC2 instance size. t3.micro: 1 vCPU, 1 GB RAM."
  type        = string
  default     = "t3.micro"
}

# ── Observability ─────────────────────────────────────────────────────────────

variable "alert_email" {
  description = "Email address for CloudWatch alarm notifications"
  type        = string
  default     = "contact@ravionics.nl"
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
}

