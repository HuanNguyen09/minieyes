# Account-level cost alarms. Created from bootstrap so they exist before any resource and survive
# `terraform destroy` of the lab.
resource "aws_budgets_budget" "cost" {
  for_each = { for l in var.limits_usd : tostring(l) => l }

  name         = "minieyes-monthly-${each.key}usd"
  budget_type  = "COST"
  time_unit    = "MONTHLY"
  limit_amount = format("%.1f", each.value)
  limit_unit   = "USD"

  notification {
    notification_type          = "ACTUAL"
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    subscriber_email_addresses = [var.alert_email]
  }

  # Early warning before the money is actually spent.
  notification {
    notification_type          = "FORECASTED"
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    subscriber_email_addresses = [var.alert_email]
  }
}
