import argparse
import time
import random
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from config import BASE_URL, build_client, LOGGER
from utils import load_cookie_dict, find_next_url, fetch_html
from storage import Storage

START_URL = f"{BASE_URL}/users/collection_actors"


def parse_actors(html: str):
    soup = BeautifulSoup(html, "lxml")

    # 1) 判别：如果没有我们期望的容器，很可能是拦截页
    if not soup.find("section"):
        LOGGER.warning(
            "解析提示：页面里没有 <section>，很可能是 Cloudflare/登录拦截页或 Cookie 失效。"
        )
    # 2) 直接用稳定选择器命中演员卡片
    boxes = soup.select("div#actors div.box.actor-box")

    items = []
    for box in boxes:
        a = box.select_one("a[href]")
        href = urljoin(BASE_URL, a["href"]) if a else None
        # 名字通常在 <strong>，回退到 a 标签的纯文本
        strong = box.select_one("strong")
        name = (
            strong.get_text(strip=True)
            if strong
            else (a.get_text(strip=True) if a else "")
        )
        if href and name:
            items.append({"href": href, "strong": name})
    return items


def crawl_all_pages(cookie_json="cookie.json"):
    # Cookie 解析逻辑集中在 utils.load_cookie_dict
    cookies = load_cookie_dict(cookie_json)
    if not cookies:
        LOGGER.error("未能从 cookie.json 解析到有效 Cookie。")
        return []

    # 建议确保包含 over18=1 & cf_clearance & _jdb_session
    for must in ("over18", "cf_clearance", "_jdb_session"):
        if must not in cookies:
            LOGGER.warning("Cookie 里没有 %s，可能会被拦截。", must)

    items = []
    with build_client(cookies) as client:
        url = START_URL
        page = 1
        LOGGER.info("开始抓取收藏演员列表")
        while url:
            LOGGER.info("抓取第 %d 页: %s", page, url)
            html = fetch_html(client, url)
            actors = parse_actors(html)
            LOGGER.info("[page %d] 解析演员 %d 条", page, len(actors))
            items.extend(actors)

            next_url = find_next_url(html)
            if next_url and next_url != url:
                url = next_url
                page += 1
                time.sleep(random.uniform(0.8, 1.6))
            else:
                url = None
    LOGGER.info("爬取收藏演员列表完成，共 %d 条。", len(items))
    return items


def run_collect_actors(
    cookie_json: str = "cookie.json", db_path: str = "userdata/actors.db"
):
    """
    抓取收藏演员列表并写入 SQLite 数据库文件，返回抓取结果列表。
    """
    data = crawl_all_pages(cookie_json)
    LOGGER.info("收藏演员抓取结果：%d 条。", len(data))
    if data:
        with Storage(db_path) as store:
            saved = store.save_actors(data)
        LOGGER.info("演员列表已写入数据库 %s（更新 %d 条）。", db_path, saved)
    else:
        LOGGER.warning("未抓取到演员数据，未写入文件。")
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="抓取收藏演员列表并写入 SQLite 数据库")
    parser.add_argument(
        "--cookie", default="cookie.json", help="Cookie JSON 路径，默认 cookie.json"
    )
    parser.add_argument(
        "--db",
        dest="db_path",
        default="userdata/actors.db",
        help="SQLite 数据库文件路径，默认 userdata/actors.db。",
    )
    args = parser.parse_args()

    run_collect_actors(cookie_json=args.cookie, db_path=args.db_path)
