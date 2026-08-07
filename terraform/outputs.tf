output "vts_private_ip" {
  description = "VtS private IP — use this in RITA's nginx config for proxy_pass"
  value       = aws_instance.vts.private_ip
}

output "vts_public_ip" {
  description = "VtS public IP (for SSH access; no EIP so this changes on stop/start)"
  value       = aws_instance.vts.public_ip
}

output "ssh_command" {
  description = "SSH into the VtS instance"
  value       = "ssh -i terraform/generated-key.pem ubuntu@${aws_instance.vts.public_ip}"
}
