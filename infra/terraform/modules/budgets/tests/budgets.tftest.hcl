mock_provider "aws" {}

variables {
  alert_email = "owner@example.com"
}

run "alarms_at_30_and_60_usd" {
  command = plan

  assert {
    condition     = toset([for b in aws_budgets_budget.cost : tonumber(b.limit_amount)]) == toset([30, 60])
    error_message = "Expected monthly cost budgets of 30 and 60 USD."
  }

  assert {
    condition = alltrue([
      for b in aws_budgets_budget.cost :
      b.budget_type == "COST" && b.time_unit == "MONTHLY" && b.limit_unit == "USD" && startswith(b.name, "minieyes-")
    ])
    error_message = "Budgets must be monthly USD cost budgets named minieyes-*."
  }

  assert {
    condition = alltrue([
      for b in aws_budgets_budget.cost : anytrue([
        for n in b.notification :
        n.notification_type == "ACTUAL" && n.threshold == 100 && n.threshold_type == "PERCENTAGE" &&
        n.comparison_operator == "GREATER_THAN" && contains(n.subscriber_email_addresses, "owner@example.com")
      ])
    ])
    error_message = "Each budget must email the owner when actual spend passes 100 %."
  }
}

run "email_is_required_and_validated" {
  command = plan

  variables {
    alert_email = "not-an-email"
  }

  expect_failures = [var.alert_email]
}
