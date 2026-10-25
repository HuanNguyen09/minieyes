# Default StorageClass backed by the aws-ebs-csi-driver add-on (Pod Identity, envs/lab).
# EKS >= 1.30 no longer marks gp2 as default, so this is the only default class.
resource "kubernetes_storage_class_v1" "gp3" {
  metadata {
    name = "gp3"
    annotations = {
      "storageclass.kubernetes.io/is-default-class" = "true"
    }
  }

  storage_provisioner    = "ebs.csi.aws.com"
  reclaim_policy         = "Delete" # destroy leaves no orphaned volumes (NFR-6)
  volume_binding_mode    = "WaitForFirstConsumer"
  allow_volume_expansion = true

  parameters = {
    type      = "gp3"
    encrypted = "true"
    # Volumes are created by the CSI controller, outside Terraform's default_tags.
    tagSpecification_1 = "Project=minieyes"
  }
}

# Argo CD bootstraps GitOps on EKS (PRD FR-PLT-1); everything after this comes from the GitOps repo.
resource "helm_release" "argocd" {
  name             = "argocd"
  repository       = "https://argoproj.github.io/argo-helm"
  chart            = "argo-cd"
  version          = var.argocd_chart_version
  namespace        = "argocd"
  create_namespace = true
  wait             = true
  timeout          = 600

  values = [yamlencode({
    # Small lab: no SSO, no notifications controller; reach the UI with kubectl port-forward.
    dex           = { enabled = false }
    notifications = { enabled = false }
    server = {
      service = { type = "ClusterIP" }
    }
    configs = {
      params = { "server.insecure" = true } # TLS terminates at Traefik once #40 lands
    }
  })]
}
