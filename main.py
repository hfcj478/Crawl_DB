import argparse

from config import LOGGER
from get_collect_actors import run_collect_actors
from get_actor_works import run_actor_works
from get_works_magnet import run_magnet_jobs
import mdcx_magnets


def main():
    parser = argparse.ArgumentParser(description="抓取收藏演员、作品及磁链的完整流程")
    parser.add_argument(
        "--cookie", default="cookie.json", help="Cookie JSON 路径，默认 cookie.json"
    )
    parser.add_argument(
        "--actors-csv",
        default="userdata/actors.csv",
        help="演员列表 CSV 输出路径，默认 userdata/actors.csv",
    )
    parser.add_argument(
        "--works-dir",
        default="userdata/works",
        help="作品 CSV 输出目录，默认 userdata/works",
    )
    parser.add_argument(
        "--magnets-dir",
        default="userdata/magnets",
        help="磁链 CSV 输出目录，默认 userdata/magnets",
    )
    parser.add_argument(
        "--tags", help="作品抓取标签过滤，逗号分隔，例如 s 或 s,d", default=None
    )
    parser.add_argument(
        "--sort-type", help="作品抓取 sort_type 参数，例如 0", default=None
    )
    parser.add_argument(
        "--skip-collect", action="store_true", help="跳过收藏演员抓取步骤"
    )
    parser.add_argument("--skip-works", action="store_true", help="跳过作品抓取步骤")
    parser.add_argument("--skip-magnets", action="store_true", help="跳过磁链抓取步骤")
    args = parser.parse_args()

    if not args.skip_collect:
        run_collect_actors(cookie_json=args.cookie, out_csv=args.actors_csv)
    else:
        LOGGER.info("跳过收藏演员抓取。")

    if not args.skip_works:
        run_actor_works(
            actors_csv=args.actors_csv,
            tags=args.tags,
            sort_type=args.sort_type,
            output_dir=args.works_dir,
            cookie_json=args.cookie,
        )
    else:
        LOGGER.info("跳过作品列表抓取。")

    if not args.skip_magnets:
        run_magnet_jobs(
            works_path=args.works_dir,
            out_root=args.magnets_dir,
            cookie_json=args.cookie,
        )
    else:
        LOGGER.info("跳过磁链抓取。")

    try:
        mdcx_magnets.run(args.magnets_dir)
    except Exception as exc:  # noqa: BLE001
        LOGGER.error("磁链筛选失败: %s", exc)


if __name__ == "__main__":
    main()
