# Budget alarms (#2) live in bootstrap: they must exist before any billable resource and keep
# watching after the lab is destroyed.
module "budgets" {
  source = "../modules/budgets"

  alert_email = var.budget_alert_email
}
