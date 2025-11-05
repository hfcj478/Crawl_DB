# get_works_magnet.py
import argparse
import time
import random
from pathlib import Path
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from config import BASE_URL, build_client, LOGGER
from utils import (
    load_cookie_dict,
    fetch_html,
)
from storage import Storage


def parse_magnets(html: str) -> List[Dict[str, Any]]:
    """
    解析 #magnets-content 下各条目：
      选择器：#magnets-content > div > div.magnet-name.column.is-four-fifths a[href]
      标签信息位于同一个 a 标签内的 div/span 结构。
    """
    soup = BeautifulSoup(html, "lxml")
    magnets: List[Dict[str, Any]] = []
    root = soup.select_one("#magnets-content")
    if not root:
        LOGGER.warning("未找到 #magnets-content（可能被拦截或页面结构变更）")
        return magnets
    entries = root.select(":scope > div")
    if not entries:
        entries = root.find_all("div", recursive=False)

    for entry in entries:
        anchor = entry.select_one(
            "div.magnet-name.column.is-four-fifths a[href^='magnet:']"
        )
        if not anchor:
            anchor = entry.select_one("a[href^='magnet:']")
        if not anchor:
            continue
        href = anchor.get("href", "").strip()
        if not href.startswith("magnet:"):
            continue

        tag_nodes = anchor.select("div span")
        tag_values = []
        for span in tag_nodes:
            classes = span.get("class") or []
            if any(cls in ("name", "meta") for cls in classes):
                continue
            text = span.get_text(strip=True)
            if text:
                tag_values.append(text)
        size_node = anchor.select_one("span.meta")
        size_value = size_node.get_text(strip=True) if size_node else ""
        magnets.append(
            {
                "href": href,
                "tags": tag_values,
                "size": size_value,
            }
        )

    if not magnets:
        for a in root.select("a[href^='magnet:']"):
            href = a.get("href", "").strip()
            if href:
                magnets.append(
                    {
                        "href": href,
                        "tags": [],
                        "size": "",
                    }
                )

    seen = set()
    deduped: List[Dict[str, Any]] = []
    for item in magnets:
        key = item["href"]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def crawl_magnets_for_row(client, code: str, href: str):
    html = fetch_html(client, href)
    magnets = parse_magnets(html)
    return magnets


def run_magnet_jobs(
    works_path: str = "userdata/works",
    out_root: str = "userdata/magnets",
    cookie_json: str = "cookie.json",
    db_path: str = "userdata/actors.db",
):
    """
    遍历数据库中的作品，抓取磁链并存入 SQLite 数据库文件。
    """
    cookies = load_cookie_dict(cookie_json)
    if not cookies:
        LOGGER.error("未能从 cookie.json 解析到有效 Cookie。")
        return {}
    for must in ("over18", "cf_clearance", "_jdb_session"):
        if must not in cookies:
            LOGGER.warning("Cookie 缺少 %s，可能会遇到拦截。", must)

    if works_path != "userdata/works":
        LOGGER.debug("works_path 参数已废弃，将被忽略：%s", works_path)
    if out_root != "userdata/magnets":
        LOGGER.debug("out_root 参数仅用于 TXT 导出，与数据库写入无关：%s", out_root)

    with Storage(db_path) as store:
        all_works = store.get_all_actor_works()
        if not all_works:
            LOGGER.warning("数据库中未找到作品数据，请先执行作品抓取。")
            return {}

        summary = {}
        with build_client(cookies) as client:
            for actor_name, works in all_works.items():
                actor_href = store.get_actor_href(actor_name) or ""
                LOGGER.info("开始抓取演员：%s", actor_name)
                magnet_counts = []
                for i, work in enumerate(works, 1):
                    code, href = work["code"], work["href"]
                    LOGGER.info("[%d/%d] %s -> %s", i, len(works), code, href)
                    try:
                        magnets = crawl_magnets_for_row(client, code, href)
                        if not magnets:
                            LOGGER.warning("%s 未解析到磁力。", code)
                        saved = store.save_magnets(
                            actor_name,
                            actor_href,
                            code,
                            magnets,
                            title=work.get("title"),
                            href=href,
                        )
                        LOGGER.info(
                            "磁链已写入数据库 %s（更新 %d 条，抓取 %d 条）。",
                            db_path,
                            saved,
                            len(magnets),
                        )
                        magnet_counts.append(saved)
                        time.sleep(random.uniform(0.8, 1.6))
                    except Exception as e:
                        LOGGER.exception("%s 抓取失败：%s", code, e)
                summary[actor_name] = {
                    "works": len(works),
                    "magnets": sum(magnet_counts),
                }
    LOGGER.info("抓取磁链完成。")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="根据数据库中的作品抓取磁链并写入 SQLite 数据库")
    parser.add_argument(
        "works_path",
        nargs="?",
        default="userdata/works",
        help="（已废弃）保留参数以兼容旧脚本，将被忽略。",
    )
    parser.add_argument(
        "--output-dir",
        default="userdata/magnets",
        help="TXT 导出目录（默认：userdata/magnets）",
    )
    parser.add_argument(
        "--cookie", default="cookie.json", help="Cookie JSON 路径，默认 cookie.json"
    )
    parser.add_argument(
        "--db",
        dest="db_path",
        default="userdata/actors.db",
        help="SQLite 数据库文件路径，默认 userdata/actors.db",
    )
    args = parser.parse_args()

    run_magnet_jobs(
        works_path=args.works_path,
        out_root=args.output_dir,
        cookie_json=args.cookie,
        db_path=args.db_path,
    )
