# 部署与安全边界

## 对外展示方式

本仓库对外只发布 GitHub Pages 静态演示。静态演示使用明确标注的脱敏样例数据，不连接 Flask、SQLite、实时行情、LLM、公司内网或本机服务。

- 静态作品页：`site/index.html`
- 静态交互演示：`site/demo.html`
- GitHub Pages 工作流：`.github/workflows/pages.yml`

禁止使用 Cloudflare Tunnel、LocalTunnel、Ngrok 等临时隧道从公司设备暴露本地服务。

## 本地运行源码

推荐 Python 3.11：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
./start-server.sh
```

默认只监听 `127.0.0.1:8766`。浏览器访问：

```text
http://127.0.0.1:8766
```

`.env`、SQLite 数据库和缓存目录不得提交到 Git。

## 经批准环境部署

动态平台只能部署在组织批准的托管环境，并接入该环境要求的身份认证、访问控制、密钥管理、审计和网络策略。仓库提供 `wsgi.py` 作为 WSGI 入口：

```bash
HOST=0.0.0.0 PORT=8766 \
gunicorn --bind 0.0.0.0:8766 --workers 1 --threads 8 --timeout 180 wsgi:app
```

上线前至少完成：

1. 身份认证与最小权限访问控制。
2. LLM、数据源 Token 进入平台密钥管理，不写入镜像或仓库。
3. SQLite 替换为受管数据库，或挂载具备备份策略的持久卷。
4. 设置允许来源、请求限流、审计日志与敏感接口保护。
5. 使用组织批准的域名、TLS、WAF 与网络出口策略。
6. 在预发布环境执行测试、依赖扫描和数据脱敏检查。

`RAGDOLL_PUBLIC_DEMO=1` 会跳过历史本地数据迁移并禁用私人 LLM/外部 CLI，但它不是身份认证或生产安全方案。
