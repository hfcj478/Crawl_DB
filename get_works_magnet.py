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
    write_magnets_csv,
    read_all_works,
    read_works_csv,
    fetch_html,
)


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
):
    """
    遍历作品 CSV 目录或单个文件，抓取磁链并写入按演员分类的 CSV。
    """
    cookies = load_cookie_dict(cookie_json)
    if not cookies:
        LOGGER.error("未能从 cookie.json 解析到有效 Cookie。")
        return {}
    for must in ("over18", "cf_clearance", "_jdb_session"):
        if must not in cookies:
            LOGGER.warning("Cookie 缺少 %s，可能会遇到拦截。", must)

    source = Path(works_path)
    if source.is_dir():
        all_works = read_all_works(str(source), base_url=BASE_URL)
    elif source.is_file():
        rows = read_works_csv(str(source), base_url=BASE_URL)
        all_works = {source.stem: rows} if rows else {}
    else:
        LOGGER.error("找不到作品路径：%s", works_path)
        return {}

    if not all_works:
        LOGGER.warning("未找到任何作品数据，停止抓取。")
        return {}

    summary = {}
    with build_client(cookies) as client:
        for actor_key, works in all_works.items():
            actor_name = actor_key.replace("_workname", "")
            LOGGER.info("开始抓取演员：%s", actor_name)
            files = []
            magnet_counts = []
            for i, w in enumerate(works, 1):
                code, href = w["code"], w["href"]
                LOGGER.info("[%d/%d] %s -> %s", i, len(works), code, href)
                try:
                    magnets = crawl_magnets_for_row(client, code, href)
                    if not magnets:
                        LOGGER.warning("%s 未解析到磁力。", code)
                    out_path = write_magnets_csv(
                        actor_name, code, magnets, out_root=out_root
                    )
                    LOGGER.info("磁链已写入 %s（共 %d 条）。", out_path, len(magnets))
                    files.append(out_path)
                    magnet_counts.append(len(magnets))
                    time.sleep(random.uniform(0.8, 1.6))
                except Exception as e:
                    LOGGER.exception("%s 抓取失败：%s", code, e)
            summary[actor_name] = {
                "files": files,
                "works": len(works),
                "magnets": sum(magnet_counts),
            }
    LOGGER.info("抓取磁链完成。")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="根据作品 CSV 抓取磁链并写入 CSV")
    parser.add_argument(
        "works_path",
        nargs="?",
        default="userdata/works",
        help="作品 CSV 目录或单个文件（默认：userdata/works）",
    )
    parser.add_argument(
        "--output-dir",
        default="userdata/magnets",
        help="磁链 CSV 输出目录，默认 userdata/magnets",
    )
    parser.add_argument(
        "--cookie", default="cookie.json", help="Cookie JSON 路径，默认 cookie.json"
    )
    args = parser.parse_args()

    run_magnet_jobs(
        works_path=args.works_path, out_root=args.output_dir, cookie_json=args.cookie
    )
