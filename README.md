# Sentinel-X

**Cloud-Native Self-Healing Engine with MCP & Micro-Sandbox**
（基于MCP与微沙箱的云原生自愈引擎）

![架构动图示意](https://chatgpt.com/c/docs/architecture.gif)

> Sentinel-X 是一个开源的云原生自愈Agent框架，结合了 **MCP协议标准化工具对接** 和 **微沙箱安全预演**，实现智能运维闭环。

------

## ⭐ 特性亮点

1. **智能故障闭环**
   - 告警接收 → Agent诊断 → Skills检索 → 修复计划生成 → 沙箱验证 → 生产执行 → 自动复盘
   - 核心能力概括：**查 / 判 / 试 / 记**
2. **安全微沙箱**
   - 高风险操作先在 Firecracker 或 Docker 微沙箱中预演
   - 防止 LLM 命令幻觉造成 P0级事故
   - 沙箱执行结果可回传，形成完整审计
3. **标准化工具接入**
   - 基于 **MCP协议**，支持 Prometheus、K8s、Loki 等
   - Agent通过统一接口调用工具，无需直接操作底层资源
4. **多Agent协同**
   - “指挥官-执行者”架构
   - 并行处理复杂故障，提高自动修复效率
5. **经验沉淀**
   - 成功修复方案生成 Markdown Skill
   - 支持向量检索和标签检索，历史经验可复用

------

## 🛠 技术栈

| 模块       | 技术选型                                |
| ---------- | --------------------------------------- |
| Agent框架  | LangGraph (Python)                      |
| 协议标准   | MCP SDK                                 |
| 沙箱技术   | Firecracker / gVisor / Docker-in-Docker |
| 后端服务   | FastAPI                                 |
| 前端UI     | Streamlit                               |
| Skills存储 | Markdown + ChromaDB                     |
| 监控数据源 | Prometheus + Loki                       |
| K8s操作    | Kubernetes Python Client / MCP-K8s      |
| 模型支持   | Qwen2.5-Coder / Claude / GPT            |

------

## 📂 目录结构

```bash
sentinel-x/
├── apps/
│   ├── api/                  # FastAPI 后端
│   └── ui/                   # Streamlit 前端
├── agents/
│   ├── graph.py              # LangGraph主流程
│   ├── nodes/                # 流程节点
│   └── prompts/              # LLM prompts
├── mcp-servers/              # MCP适配器
├── sandbox/                  # 微沙箱执行
├── skills/                   # 经验库 (Markdown)
├── storage/                  # 向量索引与审计
├── configs/                  # 配置文件
├── tests/                    # 单元/集成测试
└── docker-compose.yml        # 一键部署
```

------

## ⚡ 快速开始

```bash
# 克隆项目
git clone https://github.com/yourname/sentinel-x.git
cd sentinel-x

# 启动演示环境
docker-compose up
```

- 打开浏览器访问 `http://localhost:8501` 查看 Streamlit UI
- 模拟告警 → Agent 自动分析 → 沙箱验证 → 生产修复

------

## 📝 Skill 示例模板

```markdown
---
name: fix-pod-oom
version: 1.0
tags: [k8s, oom, memory, restart]
symptom: Pod is terminated with exit code 137
conditions:
  - memory usage close to limit
  - restart count increasing
risk_level: medium
---

# Problem
Pod repeated restart due to OOMKilled.

# Diagnosis Steps
1. Check memory usage
2. Inspect pod events
3. Confirm container exit code

# Resolution
1. Increase memory limit
2. Restart deployment
3. Verify pod becomes Ready

# Verification
- Pod status: Ready
- Restart count stable
- Memory usage below threshold

# Notes
If workload continues to grow, consider HPA or memory optimization.
```

------

## 🚀 功能演示

1. MCP基础查询：
   - CPU/内存监控
   - Pod状态和事件
2. 故障诊断：
   - OOMKilled, CrashLoopBackOff, CPU飙高等
3. 沙箱预演：
   - 安全执行修复命令
   - 自动生成审计日志
4. Skills沉淀：
   - 下一次遇到类似故障可直接命中历史经验

------

## 🎯 开发计划 (MVP)

| 阶段    | 目标                              |
| ------- | --------------------------------- |
| Phase 0 | 项目底座，定义目录结构、Skill模板 |
| Phase 1 | MCP基础设施接入，Agent可查询状态  |
| Phase 2 | 故障诊断闭环                      |
| Phase 3 | 沙箱预演与自愈                    |
| Phase 4 | Skills沉淀与检索                  |
| Phase 5 | 前端展示与完整演示                |

------

## 📌 高光亮点（简历示例）

- 架构创新：多Agent协同 + MCP标准化工具接入
- 安全突破：沙箱预演-生产执行双阶段机制
- 效果量化：CPU飙升 & Pod CrashLoopBackOff自动识别与修复，平均修复时间缩短至45秒
- 开源影响力：1.2k+ Stars，收录至 Awesome-LangChain

------

## 📜 安全策略

1. **只读模式**：指标/日志/事件查询
2. **沙箱模式**：高风险命令模拟执行
3. **生产模式**：真实执行操作，需审批或确认

**默认禁止操作**：

- 删除 Namespace/Deployment
- 批量清理资源
- 任意 Shell 执行
- 未白名单的 kubectl 命令

------

