output "instance_hostname" {
  description = "Private DNS name of the EC2 instance."
  value       = aws_instance.app_server.private_dns
}

output "instance_id" {
  description = "EC2 instance ID."
  value       = aws_instance.app_server.id
}

output "public_ip" {
  description = "Public IPv4 address used by the live HTTP feasibility test."
  value       = aws_instance.app_server.public_ip
}

output "public_dns" {
  description = "Public DNS name of the EC2 instance."
  value       = aws_instance.app_server.public_dns
}

output "health_url" {
  description = "HTTP health endpoint used by the live feasibility test."
  value       = "http://${aws_instance.app_server.public_ip}/health"
}
