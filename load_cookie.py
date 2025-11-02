from config import LOGGER
from utils import load_cookie_dict


# 读取 cookie.json 文件
def load_cookies(cookie_file="cookie.json"):
    try:
        cookies = load_cookie_dict(cookie_file)
        if cookies:
            return cookies
        LOGGER.warning("Cookie 数据不存在或无法解析！")
        return {}
    except FileNotFoundError:
        LOGGER.error(
            "Cookie 文件 %s 未找到，请确保该文件存在并包含正确的 cookie 数据。",
            cookie_file,
        )
        return {}


# 获取 Cookie 数据
cookies = load_cookies("cookie.json")
LOGGER.info("解析后的 Cookie: %s", cookies)
