## crawljav 使用说明

本项目用于抓取 [javdb.com](https://www.javdb.com) 收藏演员、作品列表与磁链数据。根据需要可一次性执行完整流程，也支持单独运行每个步骤。

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


### 完整流程

使用 `main.py` 一键执行三个阶段（收藏演员 → 作品列表 → 磁链）：

```bash
uv run python main.py \
  --cookie cookie.json \
  --actors-csv userdata/actors.csv \
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
  --output userdata/actors.csv
```

输出 CSV 默认包含列 `actor_name,href`。

#### 2. 抓取演员作品列表

```bash
uv run python get_actor_works.py \
  userdata/actors.csv \
  --tags s,d \
  --sort-type 0 \
  --output-dir userdata/works \
  --cookie cookie.json
```

- 默认读取 `userdata/actors.csv`。
- 每位演员输出一个 `{actor_name}_workname.csv`，列为 `code,href`。

也可在代码中调用 `run_actor_works(...)`，返回字典汇总每位演员写入的文件与作品数量。

#### 3. 抓取磁链信息

```bash
uv run python get_works_magnet.py \
  userdata/works \
  --output-dir userdata/magnets \
  --cookie cookie.json
```

- `userdata/works` 可以替换为某个具体的 `{actor_name}_workname.csv` 文件以针对单个演员获取磁链。
- 输出目录结构：`userdata/magnets/{actor_name}/{code}.csv`，列为 `magnet,tag,size`。

同样可直接调用 `run_magnet_jobs(...)` 获取抓取结果概览。

#### 4. 磁链筛选与导出

抓取完成后，可使用 `mdcx_magnets.py` 从每个番号的 CSV 中挑出最优磁链，生成便于复制的 TXT 文件：

```bash
uv run python mdcx_magnets.py userdata/magnets
# 仅处理当前目录，可用 --current-only
uv run python mdcx_magnets.py userdata/magnets/坂井なるは --current-only
```

- 默认会递归遍历目标目录的所有子目录，为每位演员生成同名 TXT 文件，例如 `userdata/magnets/坂井なるは/坂井なるは.txt`。
- 同一磁链不会重复追加；如果 TXT 已存在，仅写入新的条目。
- `main.py` 的完整流程会在磁链抓取结束后自动执行一次筛选。

### 常见问题

- **CSV 乱码**：脚本统一使用 `utf-8-sig` 编码，Excel 直接打开不会乱码；若已有旧文件，可重新生成或转换编码。
- **抓取失败 / 返回 0 条**：确认 Cookie 是否有效，尤其是 `cf_clearance` 是否过期。也可以查看生成的 `debug_*.html` 确认是否命中 Cloudflare 验证页。
- **访问频率**：脚本在翻页/抓取磁链时加入了随机延时（0.8~1.6 s），但仍建议适度使用，避免给目标站点造成压力或触发风控。

### 目录结构

```
userdata/
  actors.csv                 # 收藏演员列表
  works/
    某演员_workname.csv       # 该演员的作品列表
  magnets/
    某演员/
      番号.csv                # 该番号下的磁链与标签信息
  magnets/
    某演员.txt               # mdcx_magnets.py 输出的精选磁链 TXT
logs/
  2025-11-02.log             # 每日日志文件，自动追加
cookie.json                  # 你的登录 Cookie
config.py                    # 公共配置（BASE_URL、UA、build_client）
utils.py                     # 工具函数（CSV 读写、URL 构造等）
```

### 日志说明

- 所有脚本默认输出到标准输出和 `logs/<当天日期>.log`，方便排查问题。
- 如果只运行单个脚本（例如 `mdcx_magnets.py`），也会自动创建相同的日志文件并追加内容。

欢迎根据自己的需求调整输出路径或分页策略。若要扩展新的筛选条件，可在 `utils.build_actor_url` 或对应脚本中添加参数。需要更多帮助时，检查脚本命令行参数（`-h/--help`）即可查看详细说明。
