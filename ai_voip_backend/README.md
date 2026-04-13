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
```
