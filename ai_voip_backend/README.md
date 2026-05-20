# AI VoIP Backend

后端工程说明请优先参考仓库根目录的 [README](../README.md)。

本目录当前提供：

- `src/ai_voip_backend`：后端基础包与存储抽象
- `sql/pgsql`：PostgreSQL 初始化 SQL
- `docs/API.md`：当前接口文档，包含验证码登录、管理员接口与普通用户业务接口

常用命令：

```bash
uv sync
uv run ai-voip-backend list-sql
uv run ai-voip-backend bundle-sql --output build/init_pgsql.sql
uv run ai-voip-backend show-db-config
uv run ai-voip-backend check-db
uv run ai-voip-backend apply-sql
uv run ai-voip-backend bootstrap-admin --username admin --password '<PASSWORD>'
uv run ai-voip-backend show-log --type error --lines 100
uv run ai-voip-backend show-log --type info --lines 100
```

## 日志说明

后端日志默认写入当前目录下的 `log` 文件夹：

- `log/info.log`：记录请求访问、任务调度、健康检查等关键操作。
- `log/error.log`：记录异常堆栈、第三方接口调用失败、本地 ASR 连接失败等错误。

如果本地流式 ASR 检测失败，请优先查看 `error.log` 中的 endpoint 与异常详情。`127.0.0.1` 表示后端服务器本机，如果 ASR 服务部署在另一台机器，需要在语音接口配置里填写后端可访问的实际地址。
