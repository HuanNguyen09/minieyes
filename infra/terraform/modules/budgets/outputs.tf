output "budget_names" {
  description = "Names of the cost budgets."
  value       = [for b in aws_budgets_budget.cost : b.name]
}
