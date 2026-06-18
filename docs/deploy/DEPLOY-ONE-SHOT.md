# Sentinel-X 一键部署（新机开箱 · W1–W7 全栈）

> **P0 入口**：在新 Linux 服务器上，用 **一条命令** 复现 W1–W7 栈（MCP + LangGraph + cron sync + Skills + Sandbox + Patrol + 可选 UI/API/Prom）。  
> **不依赖 GitHub**：请在本机打包后 `scp` 到服务器（见下文）。

---

## 1. 前置条件（installer 不安装 k3s）

| 项 | 要求 |
|----|------|
| OS | Linux x86_64（与现网验收一致） |
| k3s | 已安装且 `kubectl get nodes` 正常；kubeconfig 默认 `/etc/rancher/k3s/k3s.yaml` |
| Docker | 可运行 `docker ps` |
| Python | 3.12+（`python3 --version`） |
| 权限 | root 或 `sudo` |
| 磁盘 | `/opt/sentinel-x` 建议 ≥ 2GB（含 venv；含 Prom 离线包时更大） |

k3s 离线安装见桌面 phase1b 指南或既有 airgap 文档；本脚本 **只检查 kubeconfig 是否存在**，不拉取 k3s 安装包。

---

## 2. 本机准备（无 GitHub 的服务器）

### 2.1 拷贝仓库

```powershell
# Windows 本机
cd C:\sentinel-x
tar czf sentinel-x.tgz --exclude=.git --exclude=**/__pycache__ --exclude=**/.langgraph_api .
scp -i C:\Users\<you>\.ssh\id_ed25519 sentinel-x.tgz root@<host>:/tmp/
```

```bash
# 服务器 — 见 §3 选择「新机」或「重装」流程
```

### 2.2 可选：Prometheus 离线包

若需要 W3 指标（`top_pods_by_cpu`），在本机先准备 `dist/kube-prometheus-offline/`（见 [DEPLOY-PROMETHEUS-K3S.md](DEPLOY-PROMETHEUS-K3S.md)），与仓库一并 scp。

---

## 3. 解压与清空（顺序很重要）

`reset-sentinel-x.sh` **在 tarball 里**；且 reset 会 **删除整个 `/opt/sentinel-x`**。  
因此：**不能**在 `/opt/sentinel-x` 解压后再跑 reset（会把刚解压的代码删掉）；**也不能**在只上传了 `.tgz`、尚未解压时直接跑 reset（脚本还不存在）。

### 3.1 新机（`/opt/sentinel-x` 从未装过）

直接解压到目标目录即可，**跳过 reset**：

```bash
mkdir -p /opt/sentinel-x
tar xzf /tmp/sentinel-x.tgz -C /opt/sentinel-x --strip-components=1   # 按 tar 顶层目录调整
find /opt/sentinel-x/deploy -name '*.sh' -exec sed -i 's/\r$//' {} +
```

### 3.2 重装（已有旧版 Sentinel-X）

**先解压到临时目录 → reset → 再解压到 `/opt/sentinel-x`**：

```bash
# 1) 解压到 staging（reset 脚本从这里执行）
mkdir -p /tmp/sentinel-x-staging
tar xzf /tmp/sentinel-x.tgz -C /tmp/sentinel-x-staging --strip-components=1
find /tmp/sentinel-x-staging/deploy -name '*.sh' -exec sed -i 's/\r$//' {} +

# 2) 清空旧栈（会删除 /opt/sentinel-x，不影响 /tmp/staging）
sudo bash /tmp/sentinel-x-staging/deploy/install/reset-sentinel-x.sh --yes
# 预览：sudo bash .../reset-sentinel-x.sh --dry-run

# 3) 正式解压到安装目录
mkdir -p /opt/sentinel-x
tar xzf /tmp/sentinel-x.tgz -C /opt/sentinel-x --strip-components=1
find /opt/sentinel-x/deploy -name '*.sh' -exec sed -i 's/\r$//' {} +
```

也可省略步骤 3，直接 `cp -a /tmp/sentinel-x-staging/. /opt/sentinel-x/`（等价于再解压一次）。

---

## 4. 一键安装

### 4.1 编辑主配置（推荐）

```bash
sudo mkdir -p /etc/sentinel
sudo cp /opt/sentinel-x/deploy/config/sentinel-x.env.example /etc/sentinel/sentinel-x.env
sudo nano /etc/sentinel/sentinel-x.env
sudo sed -i 's/\r$//' /etc/sentinel/sentinel-x.env
```

### 4.2 执行安装脚本

**最小栈**（W1–W2：K8s MCP + LangGraph + cron + 首次 sync）：

```bash
cd /opt/sentinel-x
sudo bash deploy/install/install-sentinel-x.sh
```

**W1–W7 全栈（推荐验收命令）**：

```bash
sudo bash deploy/install/install-sentinel-x.sh \
  --with-ui \
  --with-api \
  --with-prom-sync \
  --with-sandbox \
  --with-fixtures
```

| 选项 | 作用 |
|------|------|
| `--with-ui` | Streamlit systemd `:8501` |
| `--with-api` | FastAPI `:8080`（W7 webhook） |
| `--with-prom-sync` | Prom metrics sync env + 首次 prom sync |
| `--with-prometheus` | 离线 kube-prometheus（需 `dist/kube-prometheus-offline/`） |
| `--with-sandbox` | 构建 `sentinel-x-sandbox:latest`（W6） |
| `--with-fixtures` | 部署 `crash-demo` + busybox 离线导入（隐含 `--with-sandbox`） |
| `--no-patrol` | cron 不含 patrol 行（默认含 W7 patrol） |
| `--skip-sync` | 跳过首次 K8s sync |

安装过程会：

1. 创建 venv 并安装 pip 依赖  
2. `install-deploy-scripts.sh` → `/usr/local/bin/sentinel-sync-*.sh` + `sentinel-inspect-patrol.sh`  
3. MCP compose + `sentinel-config-discover/apply` → `/etc/sentinel/*.env`  
4. systemd：`sentinel-langgraph`（+ 可选 ui/api）  
5. `/etc/cron.d/sentinel-sync`（K8s sync + patrol）  
6. 可选 sandbox 镜像 + crash-demo fixture  
7. 等待 LangGraph `/ok` 并首次 sync  

---

## 5. 验证

**基线（W1–W4）**：

```bash
sudo bash /opt/sentinel-x/deploy/verify/verify-sentinel-x.sh
```

**全栈（W5–W7）**：

```bash
sudo bash /opt/sentinel-x/deploy/verify/verify-sentinel-x.sh --full
```

---

## 6. W1–W7 验收矩阵

| 周次 | 步骤 | 期望 | Live 状态 | 证据 |
|------|------|------|-----------|------|
| W1–W2 | `verify-sentinel-x.sh` | All checks passed；`list_pods count>=7` | ✅ | W25 `verify --full`；W22 baseline |
| W3 | `sentinel-sync-prom.sh` + `top_pods_by_cpu` | 含 `cpu_cores`（需 Prom 可达） | ✅（2026-06-04） | [2026-W22.md §6](../weekly/2026-W22.md) |
| W4 | SSH 隧道 `:8501` | UI 可见 pod 表 | ✅（2026-06-04） | [2026-W22.md §7](../weekly/2026-W22.md) |
| W5 | 两次 inspect 同一 CrashLoop | 第二次 narrative 含 Similar past skills | ✅（2026-06-09） | [2026-W23.md §7](../weekly/2026-W23.md) |
| W6 | `sandbox_demo.py --pod-name crash-demo`（非 dry-run） | delete ok；kube-system inspect → blocked | ✅（2026-06-09） | [2026-W23.md §7](../weekly/2026-W23.md) |
| W7 | `sentinel-inspect-patrol.sh` | `issues` 含 CrashLoop | ✅（2026-06-17） | [2026-W26.md](../weekly/2026-W26.md)：auto + cooldown |
| W7 API | `curl -X POST http://127.0.0.1:8080/v1/inspect ...` | `ok=true` | ✅ | `verify --full` 含 `/health` + POST inspect（`crash-demo` @ `sentinel-sandbox`） |
| W7 webhook | `POST /v1/webhooks/alertmanager` 样本 JSON | `issues` 含 CrashLoop | ✅ | [DEPLOY-ALERTMANAGER-WEBHOOK.md](DEPLOY-ALERTMANAGER-WEBHOOK.md) Step 1；可选 Prom receiver + rule |

W25 全栈 install 以 `verify --full` 为主验收；W3–W6 沿用 W22/W23 历史 live 记录（非 W25 当日逐项复跑）。

专题文档：

- [DEPLOY-INSPECT-LIVE.md](DEPLOY-INSPECT-LIVE.md)
- [DEPLOY-ALERT-INSPECT.md](DEPLOY-ALERT-INSPECT.md)
- [DEPLOY-ALERTMANAGER-WEBHOOK.md](DEPLOY-ALERTMANAGER-WEBHOOK.md)
- [DEPLOY-PROM-SYNC.md](DEPLOY-PROM-SYNC.md)
- [DEPLOY-UI-LIVE.md](DEPLOY-UI-LIVE.md)

---

## 7. 安装后访问

| 服务 | 地址 | 外网访问 |
|------|------|----------|
| LangGraph API | `http://127.0.0.1:2024` | `ssh -L 2024:127.0.0.1:2024 root@<host>` |
| Streamlit UI | `http://127.0.0.1:8501` | `ssh -L 8501:127.0.0.1:8501 root@<host>` |
| Sentinel API | `http://127.0.0.1:8080` | `ssh -L 8080:127.0.0.1:8080 root@<host>` |

---

## 8. 运维契约

见 [DEPLOY-REFERENCE.md](DEPLOY-REFERENCE.md)。容器重建后：

```bash
sudo bash deploy/config/sentinel-config-discover.sh --write
sudo bash deploy/config/sentinel-config-apply.sh --reload
```

---

## 9. 故障速查

| 现象 | 处理 |
|------|------|
| `ContainerConfig` compose 错误 | `docker rm` MCP 容器后重跑 install |
| MCP 0 pods | 重跑 `sentinel-sync-kubeconfig.sh` |
| busybox ImagePullBackOff | install 已尝试 daocloud + `k3s ctr import`；手补见 [sandbox/README.md](../../sandbox/README.md) |
| LangGraph 起不来 | `journalctl -u sentinel-langgraph -n 50` |
| patrol `no_candidates` | 先 sync；确认 crash-demo 在图中 |
| Prom sync 失败 | `curl http://127.0.0.1:30909/-/ready` |

---

## 10. 相关文档

| 文档 | 说明 |
|------|------|
| [DEPLOY-REFERENCE.md](DEPLOY-REFERENCE.md) | canonical 参数、env |
| [DEPLOY-SERVER.md](DEPLOY-SERVER.md) | 分步部署总索引 |
| [deploy/README.md](../../deploy/README.md) | systemd / cron / reset 脚本 |
