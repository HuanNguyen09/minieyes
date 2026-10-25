# MiniEyes — Báo cáo dự án và sổ tay vận hành

> Viết cho chính chủ dự án: đọc xong có thể **bật lại hệ thống**, **hiểu từng thành phần**, và
> **tự dựng lại từ đầu** trên một AWS account mới. Các lệnh dưới đây đã chạy thật trên hạ tầng
> lab (account `370267611220`, region `ap-southeast-1`) vào 25–26/10/2026.

---

## 1. Hệ thống làm gì (1 phút)

Camera ở nhà xưởng → AI phát hiện **người bước vào vùng nguy hiểm** (làn xe nâng…) → gửi sự kiện
lên cloud → lưu lại, có dashboard, có cảnh báo Telegram.

```text
 EDGE (nhà máy, EC2 m6i.large + k3s)                    CLOUD (AWS EKS)
 ┌───────────────────────────────────────┐   HTTPS      ┌──────────────────────────────────────┐
 │ camera-sim ──RTSP──▶ detector ──gRPC──▶│ Triton      │ Traefik (NLB) + cert-manager (TLS)    │
 │                        │  YOLOv8n      │             │   events.<domain> ─▶ event-api ─▶ PG  │
 │                        └──── event ────┼────────────▶│   metrics.<domain> ─▶ Prometheus      │
 │ Alloy (metrics + logs) ────────────────┼────────────▶│   logs.<domain>    ─▶ Loki            │
 │ Argo CD (kéo cấu hình từ Git)          │             │   grafana.<domain> ─▶ Grafana         │
 └───────────────────────────────────────┘             │ Argo CD, Alertmanager ─▶ Telegram      │
        chỉ có kết nối ĐI RA                            └──────────────────────────────────────┘
```

Ý tưởng cốt lõi: **edge không mở cổng vào** (giống thiết bị sau NAT/firewall của khách hàng).
Mọi thứ từ edge đều là kết nối đi ra: Argo CD kéo cấu hình, Alloy đẩy metrics/logs, detector đẩy
event.

---

## 2. Bản đồ repository

| Đường dẫn | Là gì | Kiểm thử |
|---|---|---|
| `apps/detector` | Python: RTSP → letterbox → Triton → postprocess → vùng → debounce → publisher | 70 unit + integration |
| `apps/event-api` | FastAPI + SQLAlchemy + Alembic, API key theo site, phân trang cursor | 65 unit + 47 trên Postgres thật |
| `triton/` | Export YOLOv8n → ONNX, `config.pbtxt`, image chứa model | 3 unit + smoke |
| `camera-sim/` | MediaMTX + ffmpeg phát lại video mẫu thành RTSP | healthcheck ffprobe |
| `compose.yaml` | Toàn bộ hệ thống trên 1 máy (OVMS thay Triton) | 3 e2e |
| `charts/` | Helm: detector, event-api, triton, camera-sim, platform | 70 helm-unittest + kubeconform |
| `infra/terraform` | bootstrap (state, budget), envs/lab (VPC, EKS, edge, ECR, OIDC), envs/lab-platform (Argo CD, gp3) | 41 `terraform test` |
| `infra/ansible` | common, k3s, node_exporter, argocd cho edge | Molecule + chạy thật |
| `infra/aws/iam` | Policy deployer, guardrails, boundary, operator | 7 test bất biến |
| `infra/aws/devbox` | Script bootstrap dev box (một lần, bằng admin) | đã chạy thật |
| `observability/` | Alert rules, Alertmanager, values cho Prometheus/Loki/Alloy | promtool, amtool |
| `gitops/` | **Seed** cho repo `minieyes-gitops` (repo thật nằm riêng) | 35 test bất biến |
| `scripts/` | `devbox.sh`, `bootstrap-secrets.sh`, `edge-kubeconfig.sh`, `seed-gitops.sh`, `check-charts.sh`, `k3d.sh` | — |
| `docs/adr` | 5 quyết định kiến trúc (AWS, pull GitOps, Alloy, không NAT, OVMS local) | — |

Repo thứ hai: **`HuanNguyen09/minieyes-gitops`** — trạng thái mong muốn của từng cluster. Argo CD
đọc repo này; **sửa cluster = sửa repo này** (không `kubectl apply` tay).

---

## 3. Hạ tầng AWS đang có

| Thành phần | Tên / giá trị | Ghi chú |
|---|---|---|
| Dev box (máy điều phối) | `minieyes-devbox` `i-065460e31e1a61966`, EIP `54.169.211.248` | t3.xlarge, VPC riêng `minieyes-devbox`, không mở cổng, vào bằng SSM |
| State Terraform | S3 `minieyes-tfstate-370267611220` | versioning, mã hoá, `prevent_destroy` |
| Budget | 30 USD và 60 USD/tháng → email | nằm trong `bootstrap`, sống sót khi xoá lab |
| EKS | `minieyes-lab` (Kubernetes 1.35), 3 node Spot t3.medium | public subnets, không NAT (ADR-004) |
| Edge | `minieyes-edge` `i-09bcaddf9f539c5b3`, EIP `18.136.78.130` | m6i.large, k3s v1.36, SSH chỉ từ dev box |
| ECR | `minieyes/{detector,event-api,camera-sim,model-yolov8n}` | tag bất biến = git SHA đầy đủ, scan on push |
| Domain | `13-229-14-139.sslip.io` (IP của NLB) | `events.`, `metrics.`, `logs.`, `grafana.` |
| Secret | SSM Parameter Store `/minieyes/*` (SecureString) | tạo bởi `scripts/bootstrap-secrets.sh` |

### Mô hình quyền (quan trọng nhất về bảo mật)

| Danh tính | Ở đâu | Làm được | Credential |
|---|---|---|---|
| Root/admin | — | chỉ dùng **một lần** để chạy `infra/aws/devbox/bootstrap.sh` | **đã xoá khỏi máy** |
| `operator-minieyes` | profile `minieyes-operator` trên laptop | bật/tắt dev box, gửi lệnh SSM vào dev box | access key (không bao giờ in ra) |
| `DevBox-MiniEyes-Claude` | role của dev box | Terraform/ECR/EKS trong guardrails | không có key |
| `minieyes-*` (do Terraform tạo) | EKS, node, edge, GitHub | phần việc của từng workload | luôn có **permissions boundary** |

Chặn **Bedrock / SageMaker / Q / Marketplace** ở mọi tầng; chỉ region Singapore; chỉ loại máy rẻ;
không tạo user/key; không `sts:AssumeRole`; không đụng tài nguyên không gắn tag `Project=minieyes`.
Chi tiết và rủi ro còn lại: `infra/aws/iam/README.md`.

---

## 4. Bật lại hệ thống vào buổi sáng (sau khi đã "tắt tiết kiệm")

Tối 25/10 đã: scale node group EKS về 0, stop edge, stop dev box. **Control plane EKS và NLB vẫn
chạy** (~0,12 USD/giờ) để sáng không phải dựng lại. Bật lại (từ laptop, Git Bash):

```bash
cd C:/DATA/website/cv/minieyes
# 1. dev box
MSYS_NO_PATHCONV=1 aws ec2 start-instances --instance-ids i-065460e31e1a61966 \
  --profile minieyes-operator --region ap-southeast-1
# đợi ~1 phút cho SSM online, rồi mọi lệnh khác chạy QUA dev box:
bash scripts/devbox.sh 'cd ~/minieyes && git pull -q && bash scripts/lab-power.sh up'
# 2. kiểm tra
bash scripts/devbox.sh 'bash ~/minieyes/scripts/lab-power.sh status'
```

`scripts/lab-power.sh up` làm: start edge → scale node group về 3 → chờ node Ready → mở lại SSH
tunnel tới edge. Argo CD tự đồng bộ lại mọi thứ (5–10 phút). Dữ liệu Postgres còn nguyên (volume
EBS không bị xoá khi scale về 0).

Thử nhanh:

```bash
bash scripts/devbox.sh 'curl -s https://events.13-229-14-139.sslip.io/healthz'
bash scripts/devbox.sh 'kubectl --context edge-01 -n minieyes logs deploy/detector --tail 5'
```

Tắt lại buổi tối: `bash scripts/devbox.sh 'bash ~/minieyes/scripts/lab-power.sh down'`, rồi
stop dev box bằng `aws ec2 stop-instances … --profile minieyes-operator`.

Từ laptop, mọi host trả **403** (đã kiểm tra) vì chỉ IP dev box và edge được phép.
Xem Grafana / Argo CD từ dev box:
`https://grafana.13-229-14-139.sslip.io` (user `admin`, mật khẩu ở SSM
`/minieyes/cloud/grafana-password`). Muốn mở từ laptop: thêm IP laptop vào
`clusters/cloud/values/platform.yaml → traefik.sourceRanges` trong repo GitOps.

---

## 5. Dựng lại từ đầu trên account mới (thứ tự bắt buộc)

| # | Việc | Lệnh / file | Thời gian |
|---|---|---|---|
| 1 | Bootstrap quyền + dev box (admin, **một lần**) | `AWS_PROFILE=<admin> MSYS_NO_PATHCONV=1 bash infra/aws/devbox/bootstrap.sh` rồi **xoá admin key** | 5' |
| 2 | Vào dev box, kéo code | `scripts/devbox.sh` (từ laptop) | — |
| 3 | State + budget | `infra/terraform/bootstrap`: `terraform apply` (biến `budget_alert_email`) | 2' |
| 4 | Gắn EIP cố định cho dev box | xem mục 7 "EIP" | 1' |
| 5 | Mạng, EKS, edge, ECR, OIDC | `envs/lab`: `terraform.tfvars` (admin_cidr = EIP dev box /32, SSH key) → plan → apply | 20' |
| 6 | Argo CD + gp3 | `envs/lab-platform`: plan → apply | 5' |
| 7 | Build + push image (tag = SHA đầy đủ) | export model, `docker build/push` 4 image | 10' |
| 8 | Repo GitOps | `scripts/seed-gitops.sh` với `BASE_DOMAIN=pending.sslip.io` → push | 2' |
| 9 | Secret cloud | `scripts/bootstrap-secrets.sh cloud` | 1' |
| 10 | Bật GitOps cloud | `kubectl apply -f <gitops>/clusters/cloud/root.yaml` | 10' |
| 11 | Domain thật | lấy IP của NLB Traefik → thay `pending.sslip.io` bằng `<ip-gạch-ngang>.sslip.io` trong repo GitOps | 5' |
| 12 | Edge | `infra/ansible`: `EDGE_HOST=… ADMIN_CIDR=… ansible-playbook site.yml` | 8' |
| 13 | Secret edge | `scripts/edge-kubeconfig.sh` rồi `scripts/bootstrap-secrets.sh edge` | 1' |

---

## 6. Những việc khó và các "bẫy" đã gặp (đọc kỹ phần này)

### Thiết kế / kiến trúc

1. **Edge sau NAT ⇒ GitOps kiểu pull.** CI không thể `kubectl` vào nhà máy, nên mỗi cluster tự
   chạy Argo CD và kéo cấu hình. Rollback = `git revert`. (ADR-002)
2. **Chỉ giữ frame mới nhất.** Inference chậm hơn camera; nếu xếp hàng frame thì độ trễ tăng mãi.
   `FrameSource` ghi đè frame cũ và đếm vào `minieyes_frames_dropped_total`. Trên CPU khoảng
   1/3 frame bị bỏ — đó là thiết kế, không phải lỗi.
3. **Không mất event khi mất mạng.** Publisher có buffer 1.000 event, retry theo backoff (1→30 s,
   ±20 %), 401 = lỗi cấu hình (không retry), 4xx khác = bỏ, 5xx/429/mất kết nối = giữ lại. API
   idempotent theo `event_id` (unique index) nên gửi lại không sinh bản trùng. E2E đã chứng minh:
   tắt API 30 s, số event lưu = `events_total − events_dropped_total`.
4. **Phiên bản đi cùng nhau.** Trong repo GitOps, `targetRevision` của chart và `image.tag` phải là
   **cùng một commit SHA đầy đủ** (có test kiểm tra). Code, chart, image không bao giờ lệch nhau.
5. **Triton 15 GB.** Không vừa laptop/CI ⇒ local và CI dùng **OVMS** (cùng giao thức KServe v2,
   detector không đổi dòng code nào); cluster thật chạy Triton. (ADR-005)
6. **Model là image OCI.** `.onnx` không vào Git (giấy phép AGPL + dung lượng) ⇒ đóng gói thành
   image `minieyes/model-yolov8n`, initContainer copy vào Triton. Model có version và được scan như app.

### Bẫy đã gặp khi chạy thật (và cách sửa đã nằm trong code)

| Triệu chứng | Nguyên nhân | Đã sửa bằng |
|---|---|---|
| `terraform apply` lab lỗi `EntityAlreadyExists` | Account đã có GitHub OIDC provider (dự án khác). Mỗi URL chỉ có 1 provider | Module dùng lại provider có sẵn qua data source (`create_provider=false`) — **không import**, vì destroy lab sẽ xoá mất của dự án kia |
| Pod `Pending: Too many pods` | Spot chọn **t3.small**: VPC CNI chỉ cho 11 pod/node, ~1,4 GiB RAM | Bỏ t3.small, 3 node t3.medium/m6i.large |
| Argo CD không render Traefik | Chart Traefik 41 đổi schema: `ports.web.redirections` → `ports.web.http.redirections` | Sửa values + test |
| Sync của `platform` treo vô hạn | Lần sync cũ chờ Ingress "healthy" mà Traefik chưa chạy ⇒ revision mới không được áp dụng | Terminate operation (`status.operationState.phase=Terminating`) để Argo sync lại |
| Chứng chỉ Let's Encrypt `pending` mãi | `loadBalancerSourceRanges` trên NLB chặn luôn máy chủ xác thực của Let's Encrypt ở cổng 80 | Lọc IP ở **tầng Traefik** (middleware `ipAllowList`), NLB để mở; route ACME không có middleware |
| Migration Job chạy trước Postgres | Hook `PreSync` chạy trước cả StatefulSet trong lần sync đầu | Sync waves: Postgres −1 → migrate (Sync hook) 0 → API 1 |
| API không bao giờ được tạo, Argo retry mãi | HPA ở wave 0 báo `Degraded` ("target not found") vì Deployment ở wave 1 chưa có | HPA chuyển sang wave 2 |
| `event-api` vẫn `Degraded` dù API chạy | EKS **không có sẵn metrics-server** ⇒ HPA không đọc được CPU | Thêm EKS add-on `metrics-server` |
| NetworkPolicy "có" nhưng không chặn gì trên EKS | Add-on `vpc-cni` chưa bật network policy agent | `enableNetworkPolicy=true`; đã thử: pod debug → Postgres bị **BLOCKED** |
| Ansible lần 2 vẫn `changed=2` | Secret dùng `stringData` ⇒ `kubectl apply` luôn báo `configured` | Dùng `data` (base64); lần chạy lại `changed=0` |
| Argo vẫn báo lỗi cũ sau khi đã sửa | Kết quả render bị cache | `argocd.argoproj.io/refresh=hard` |
| `sshd -t` lỗi trong Molecule | Ubuntu 24.04 khởi động sshd bằng socket ⇒ `/run/sshd` chưa có | Role tạo thư mục trước khi kiểm tra |
| cloud-init dev box dừng giữa chừng | Bản trivy v0.56.2 không còn file tải; tên binary helm-unittest khác | Pin trivy v0.75.0, sửa tên |
| Script `.sh` hỏng trên Linux | File viết trên Windows có CRLF | `.gitattributes eol=lf`; luôn kiểm `file x.sh` |
| `aws ssm get-parameter /aws/service/...` lỗi trên Git Bash | Git Bash tự đổi `/aws/...` thành đường dẫn Windows | `MSYS_NO_PATHCONV=1` |
| Hai lệnh `devbox.sh` chạy song song phá nhau | Dùng chung `/tmp/devbox-cmd.sh`; bash đọc script trong lúc chạy | Mỗi lần một file `mktemp` |
| Default VPC không có subnet | Account đã xoá subnet mặc định | Dev box có VPC riêng, không đụng VPC khác của bạn |
| E2E fail ở lần chạy thứ 2 | Postgres giữ event cũ, còn metric detector đếm lại từ 0 | Chỉ so các event từ lúc process detector khởi động |

### Bảo mật

- **Không bao giờ dán key vào chat/file trong repo.** Root key đã từng nằm trong `.env` — đã xoá
  khỏi máy; **hãy chắc chắn đã Delete trong console** (Security credentials → Access keys).
- Secret ứng dụng chỉ nằm ở SSM `/minieyes/*` và trong cluster; GitOps repo không có secret nào.
- Pod Security **restricted** cho namespace `minieyes` (mọi pod đã đạt, có test); `monitoring`
  là privileged vì node-exporter và Alloy cần truy cập host (ghi rõ là ngoại lệ).
- NetworkPolicy mặc định chặn hết: Postgres chỉ nhận từ event-api; detector chỉ được gọi DNS,
  Triton, camera và HTTPS ra ngoài.
- Rủi ro còn lại (chấp nhận cho lab): role `minieyes-*` có thể bị đổi trust sang account ngoài
  (vẫn bị boundary giới hạn); deployer có `ec2:*` trên network của VPC khác. Cách mạnh nhất: một
  AWS account riêng cho dự án + SCP chặn Bedrock.

### Chi phí

| Trạng thái | Ước tính |
|---|---|
| Chạy đầy đủ | ~0,35 USD/giờ (~8 USD/ngày): EKS 0,10 + 3 node Spot ~0,05 + edge 0,12 + dev box 0,21 khi bật + NLB/EBS/IP |
| "Tắt tiết kiệm" (node 0, edge + dev box stop) | ~0,13 USD/giờ (~3 USD/ngày): control plane EKS, NLB, EBS, EIP |
| Xoá hẳn | `terraform destroy` lab-platform → lab (giữ bootstrap). Trước đó xoá Service LoadBalancer của Traefik và các PVC, nếu không NLB/EBS chặn destroy |

Credit của account trả cho EKS, EC2, ECR, ELB, VPC, S3, SSM, KMS, CloudWatch (đã đối chiếu danh sách).

---

## 7. Lệnh hay dùng (copy được)

```bash
# chạy lệnh trên dev box từ laptop
bash scripts/devbox.sh '<lệnh>'                      # TIMEOUT=3600 cho việc dài
# EKS / edge
kubectl config use-context $(kubectl config get-contexts -o name | grep minieyes-lab)
bash scripts/edge-kubeconfig.sh && kubectl --context edge-01 get pods -A
# Argo CD ép refresh / dừng sync bị treo
kubectl -n argocd annotate app <app> argocd.argoproj.io/refresh=hard --overwrite
kubectl -n argocd patch app <app> --type json \
  -p '[{"op":"replace","path":"/status/operationState/phase","value":"Terminating"}]'
# xem event
curl -s -H "X-API-Key: $(aws ssm get-parameter --name /minieyes/site-01/api-key --with-decryption \
  --query Parameter.Value --output text)" "https://events.13-229-14-139.sslip.io/events?limit=5"
# EIP cho dev box (giữ admin_cidr cố định)
aws ec2 allocate-address --domain vpc --tag-specifications \
  'ResourceType=elastic-ip,Tags=[{Key=Name,Value=minieyes-devbox},{Key=Project,Value=minieyes}]'
# kiểm thử toàn bộ (trên dev box)
make test test-helm test-tf test-rules test-ansible && make e2e
```

---

## 8. Việc còn lại

| Issue | Còn thiếu | Cần gì |
|---|---|---|
| #27, #28, #30 CI | Workflow GitHub Actions chưa push | Token GitHub cần scope `workflow`: `gh auth refresh -h github.com -s workflow -u HuanNguyen09` |
| #35 Dashboards | Chưa có JSON dashboard | Có thể làm tiếp |
| #38 Failure drills | Chưa diễn tập (tắt camera, tắt API, xoá pod…) | Có runbook cho từng alert |
| #39 Demo, README cuối | Chưa quay video | — |
| Telegram | `/minieyes/cloud/telegram-bot-token` đang là giá trị ngẫu nhiên | Tạo bot với BotFather, ghi token vào SSM, chạy lại `bootstrap-secrets.sh cloud`, sửa `chat_id` |
| Repo GitOps CI | `ci/validate.yaml` chưa chuyển vào `.github/workflows` | Cùng lý do scope `workflow` |
