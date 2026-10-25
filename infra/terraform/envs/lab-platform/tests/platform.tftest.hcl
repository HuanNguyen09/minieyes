mock_provider "aws" {
  mock_data "aws_eks_cluster" {
    defaults = {
      endpoint = "https://ABCDEF.gr7.ap-southeast-1.eks.amazonaws.com"
      certificate_authority = [{
        data = "Y2VydA==" # base64("cert")
      }]
    }
  }
}

mock_provider "helm" {}

mock_provider "kubernetes" {}

run "argocd_chart_is_pinned" {
  command = plan

  assert {
    condition     = helm_release.argocd.chart == "argo-cd" && helm_release.argocd.repository == "https://argoproj.github.io/argo-helm"
    error_message = "Argo CD must come from the official argo-helm repository."
  }

  assert {
    condition     = can(regex("^[0-9]+\\.[0-9]+\\.[0-9]+$", helm_release.argocd.version))
    error_message = "Argo CD chart version must be pinned to an exact version."
  }

  assert {
    condition     = helm_release.argocd.namespace == "argocd" && helm_release.argocd.create_namespace
    error_message = "Argo CD must be installed into its own argocd namespace."
  }
}

run "gp3_is_the_default_storage_class" {
  command = plan

  assert {
    condition     = kubernetes_storage_class_v1.gp3.metadata[0].name == "gp3"
    error_message = "StorageClass must be named gp3."
  }

  assert {
    condition     = kubernetes_storage_class_v1.gp3.metadata[0].annotations["storageclass.kubernetes.io/is-default-class"] == "true"
    error_message = "gp3 must be the default StorageClass."
  }

  assert {
    condition = (
      kubernetes_storage_class_v1.gp3.storage_provisioner == "ebs.csi.aws.com" &&
      kubernetes_storage_class_v1.gp3.parameters["type"] == "gp3" &&
      kubernetes_storage_class_v1.gp3.parameters["encrypted"] == "true"
    )
    error_message = "gp3 StorageClass must use the EBS CSI driver with encrypted gp3 volumes."
  }

  assert {
    condition     = kubernetes_storage_class_v1.gp3.volume_binding_mode == "WaitForFirstConsumer"
    error_message = "Volumes must be created in the AZ of the consuming pod."
  }
}
