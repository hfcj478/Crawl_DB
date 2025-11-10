## crawljav 使用说明

本项目用于抓取 [番] 收藏演员、作品列表与磁链数据，并以 SQLite 数据库集中存储。根据需要可一次性执行完整流程，也支持单独运行每个步骤。

> **注意**：抓取依赖你自己的登录 Cookie。请自行承担访问目标站点的风险，并遵守站点规则与当地法规。

### 环境准备

1. 安装依赖（推荐使用 [uv](https://github.com/astral-sh/uv) 或 `pip`）：
   ```bash
   uv sync
   # 或
   pip install -r requirements.txt  # 若使用 pip，请确保 requirements 文件指向 pyproject 中的依赖
   ```
2. 准备 `cookie.json`，内容示例：
   ```json
   {
     "cookie": "over18=1; cf_clearance=xxx; _jdb_session=yyy"
   }
   ```
3. 数据库初始化：首次运行 `main.py` 会自动创建 `userdata/actors.db` 并执行 `schema.sql`。若需手动初始化，可执行：
   ```bash
   mkdir -p userdata
   sqlite3 userdata/actors.db < schema.sql
   ```

### 完整流程

使用 `main.py` 一键执行三个阶段（收藏演员 → 作品列表 → 磁链，外加磁链筛选）：

```bash
uv run python main.py \
  --cookie cookie.json \
  --db-path userdata/actors.db \
  --works-dir userdata/works \
  --magnets-dir userdata/magnets \
  --tags s,d \
  --sort-type 0
```

- `--tags`、`--sort-type` 可选，用于作品筛选，留空表示抓全部。
- 可通过 `--skip-collect` / `--skip-works` / `--skip-magnets` 跳过某个阶段，例如已有演员列表时跳过第一步。

### 单独运行各阶段

#### 1. 抓取收藏演员列表

```bash
uv run python get_collect_actors.py \
  --cookie cookie.json \
  --db userdata/actors.db
```

默认写入 SQLite 数据库 `actors` 表，可通过 `sqlite3 userdata/actors.db` 查看数据。

#### 2. 抓取演员作品列表

```bash
uv run python get_actor_works.py \
  --db userdata/actors.db \
  --tags s,d \
  --sort-type 0 \
  --output-dir userdata/works \
  --cookie cookie.json
```

- 默认读取 `userdata/actors.db`，无需再准备 CSV。
- 作品数据写入数据库 `works` 表，可在 `storage.py` 中查看表结构定义。

也可在代码中调用 `run_actor_works(...)`，返回字典汇总每位演员写入的文件与作品数量。

#### 3. 抓取磁链信息

```bash
uv run python get_works_magnet.py \
  userdata/works \
  --output-dir userdata/magnets \
  --cookie cookie.json \
  --db userdata/actors.db
```

- `userdata/works` 参数仅保留兼容性，磁链数据写入数据库 `magnets` 表，同时仍会在 `userdata/magnets/{actor_name}/{code}.csv` 中输出最新抓取结果，便于查看。

同样可直接调用 `run_magnet_jobs(...)` 获取抓取结果概览。

#### 4. 磁链筛选与导出

抓取完成后，可使用 `mdcx_magnets.py` 从数据库中挑出每个番号的最优磁链，生成便于复制的 TXT 文件：

```bash
uv run python mdcx_magnets.py \
  userdata/magnets \
  --db userdata/actors.db
# 仅处理当前目录，可用 --current-only
uv run python mdcx_magnets.py userdata/magnets/坂井なるは --current-only --db userdata/actors.db
```

- 默认会递归遍历目标目录的所有子目录，为每位演员生成同名 TXT 文件，例如 `userdata/magnets/坂井なるは/坂井なるは.txt`；TXT 内容来自数据库中的最佳磁链。
- 同一磁链不会重复追加；如果 TXT 已存在，仅写入新的条目。
- `main.py` 的完整流程会在磁链抓取结束后自动执行一次筛选。

### 常见问题

- **CSV 乱码**：脚本统一使用 `utf-8-sig` 编码，Excel 直接打开不会乱码；若已有旧文件，可重新生成或转换编码。
- **抓取失败 / 返回 0 条**：确认 Cookie 是否有效，尤其是 `cf_clearance` 是否过期。也可以查看生成的 `debug_*.html` 确认是否命中 Cloudflare 验证页。
- **访问频率**：脚本在翻页/抓取磁链时加入了随机延时（0.8~1.6 s），但仍建议适度使用，避免给目标站点造成压力或触发风控。

### 目录结构

```
userdata/
  actors.db                  # SQLite 数据库（actors / works / magnets 三张表）
  works/                     # 旧版 CSV 输出目录（仍可保留）
  magnets/
    某演员/
      番号.csv                # 最近一次磁链抓取的 CSV 备份
    某演员.txt               # mdcx_magnets.py 输出的精选磁链 TXT
logs/
  2025-11-02.log             # 每日日志文件，自动追加
cookie.json                  # 你的登录 Cookie
schema.sql                   # 数据库结构定义（供手动初始化使用）
config.py / storage.py / utils.py 等核心脚本
```

### 日志说明

- 所有脚本默认输出到标准输出和 `logs/<当天日期>.log`，方便排查问题。
- 如果只运行单个脚本（例如 `mdcx_magnets.py`），也会自动创建相同的日志文件并追加内容。

欢迎根据自己的需求调整输出路径或分页策略。若要扩展新的筛选条件，可在 `utils.build_actor_url` 或对应脚本中添加参数。需要更多帮助时，检查脚本命令行参数（`-h/--help`）即可查看详细说明。
