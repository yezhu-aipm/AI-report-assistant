# 部署指南

> 适用于 Ubuntu 22.04 / 24.04。2 核 2G 的入门云服务器就能跑，安装脚本会自动适配小内存。

## 1. 准备服务器

- **机型**：2 核 2G 就够用，比如阿里云 ECS e 实例。系统选 **Ubuntu 24.04 64位**。
- **安全组**：入方向放行 **80** 端口（来源 `0.0.0.0/0`）；以后有了域名再放行 443。
- **备案**：用国内服务器、通过**域名**访问，要先做 ICP 备案；只用**公网 IP** 访问不需要备案，可以先这样用起来。

## 2. 安装

1. 从 [Releases](https://github.com/yezhu-aipm/ai-report-assistant/releases) 下载 `xueqing-release.zip`。这个包里已经有打包好的前端。
2. 把 zip 上传到服务器的 `/root`。可以用云厂商控制台网页终端自带的文件上传，或者用 `scp`。
3. 在服务器上运行：

```bash
apt-get update && apt-get install -y unzip && cd /root && unzip -o xueqing-release.zip && cd xueqing && bash deploy/install.sh
```

安装脚本会自动完成这些事：

| 步骤 | 内容 |
|---|---|
| 小内存适配 | 内存小于 3G 时，加 2G 虚拟内存，并设置一次只处理一个任务 |
| 依赖 | Python、中文字体、Nginx、fail2ban、sqlite3。pip 用阿里云镜像，Chromium 用 npmmirror 镜像 |
| 服务 | 注册为 systemd 服务，开机自动启动 |
| 网页入口 | 自动配置用 IP 访问的 Nginx，带访问频率限制 |
| 安全 | fail2ban 防 SSH 暴力破解 |
| 备份 | 每天 3:30 自动备份，保留 7 天 |
| 邀请码 | 第一次安装时随机生成一个，并显示在屏幕上 |

看到 `安装完成。浏览器打开：http://服务器IP` 就成功了。**第一个注册的账号自动成为管理员。**

## 3. 填大模型 Key

Key 只保存在服务器上。下面这种方式粘贴时屏幕上不显示，也不会留在命令历史里：

```bash
read -s -p "请粘贴 API Key 后按回车: " K && sed -i "s|^LLM_API_KEY=.*|LLM_API_KEY=$K|" /opt/xueqing/.env && unset K && systemctl restart xueqing && echo " 已保存并重启"
```

再把 `LLM_BASE_URL` 和两个模型名改成你用的服务商的（见 `.env.example` 里的示例），然后运行 `systemctl restart xueqing`。

不填 Key 也能用，这就是**演示模式**：只能读 Excel / Word 表格，报告文字用模板生成，适合先试跑。

## 4. 配域名和 HTTPS（备案之后）

1. 在云厂商控制台把域名解析到服务器 IP，再申请一张免费 SSL 证书，下载 Nginx 格式。
2. 把证书放到 `/etc/nginx/ssl/`，修改 `deploy/nginx.conf` 里的域名和证书文件名，然后：

```bash
sudo cp /opt/xueqing/deploy/nginx.conf /etc/nginx/conf.d/xueqing.conf
sudo nginx -t && sudo systemctl reload nginx
```

3. HTTPS 能打开之后，把 `.env` 里的 `COOKIE_SECURE` 改成 `true`，重启服务。安全组记得放行 443 端口。

## 日常维护

| 要做的事 | 命令 |
|---|---|
| 查看运行状态 | `sudo systemctl status xueqing` |
| 查看最近日志 | `sudo journalctl -u xueqing -n 100` |
| 重启 | `sudo systemctl restart xueqing` |
| 备份数据 | 已经自动备份：每天 3:30 备份到 `/var/backups/xueqing`，保留 7 天；手动备份运行 `sudo /opt/xueqing/deploy/backup.sh` |
| 更新版本 | 上传新的发布包，然后运行 `cd /root && rm -rf xueqing && unzip -o xueqing-release.zip && cd xueqing && bash deploy/install.sh`，数据和 `.env` 会保留 |
| 更换邀请码 | 管理员登录后，在「设置 → 管理员」里修改 |
| 关闭注册 | `.env` 里 `ALLOW_REGISTER=false`，重启 |

## 材料怎么准备最准

- **成绩表和出门测表用 Excel 最准**，系统直接读表格，不经过大模型。网站上传页面可以下载两份模板。
  - 成绩表：表头一行「姓名 | 1 | 2 | … | 14(1) | … | 总分」，可以加一行「满分」。
  - 出门测表：第一行写讲次（合并单元格横跨这一讲的知识点），第二行写知识点，答对填 ✔ 或 1，答错填 × 或 0。
- **试卷**可以是 PDF、图片或 Word，由大模型识别题型、分值、知识点和讲次；也可以直接上传「题号 | 题型 | 分值 | 知识点 | 讲次」的题目表。
- 拍照的成绩表、出门测表也能识别，识别没把握的格子会标黄让老师确认。

## 用 Docker 部署（可选）

```bash
cp .env.example .env   # 修改配置
docker compose up -d --build
```

国内服务器拉取 Docker Hub 镜像经常失败，需要先在云厂商控制台开通镜像加速，所以更推荐上面的一键安装脚本。

## 本地开发

```bash
# 后端
cd backend && pip install -r requirements.txt && python -m playwright install chromium   # 没有 .env 时自动进入演示模式
uvicorn app.main:app --reload --port 8000
# 前端（另开一个终端）
cd frontend && npm install && npm run dev     # 打开 http://localhost:5173
```

接口文档：启动后访问 `/api/docs`。
