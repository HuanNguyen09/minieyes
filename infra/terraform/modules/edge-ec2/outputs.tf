output "public_ip" {
  description = "Elastic IP of the edge (Ansible inventory; NLB loadBalancerSourceRanges in #40)."
  value       = aws_eip.edge.public_ip
}

output "instance_id" {
  description = "Edge instance id."
  value       = aws_instance.edge.id
}

output "security_group_id" {
  description = "Edge security group (drill 6 removes its egress rule)."
  value       = aws_security_group.edge.id
}
