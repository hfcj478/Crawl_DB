from __future__ import annotations

import argparse
import csv
import logging
import re
from pathlib import Path
from typing import Iterable, Optional, Sequence


LOGGER = logging.getLogger("crawljav.mdcx_magnets")
KEYWORDS = {"高清", "字幕"}
SIZE_PATTERN = re.compile(r"([\d.]+)\s*GB", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "根据磁链体积和关键标签，从目录中的每个 CSV 文件挑选最佳磁链，"
            "并写入以目录名命名的 txt 文件。"
        )
    )
    parser.add_argument(
        "directory",
        type=Path,
        help="包含 magnet、tags、size 列的 CSV 文件所在目录。",
    )
    parser.add_argument(
        "-c",
        "--current-only",
        action="store_true",
        help="仅处理指定目录，不递归子目录。",
    )
    return parser.parse_args()


def extract_size(size_field: Optional[str]) -> Optional[float]:
    if not size_field:
        return None
    match = SIZE_PATTERN.search(size_field)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def count_keyword_hits(tags_field: Optional[str]) -> int:
    if not tags_field:
        return 0
    tags = [segment.strip() for segment in tags_field.split(",")]
    return sum(1 for tag in tags if tag in KEYWORDS)


def pick_best_magnet(csv_path: Path) -> Optional[str]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        best_magnet: Optional[str] = None
        best_size = -1.0
        best_keyword_hits = -1

        for row in reader:
            magnet = row.get("magnet")
            if not magnet:
                continue

            size_value = extract_size(row.get("size"))
            if size_value is None:
                continue

            keyword_hits = count_keyword_hits(row.get("tags"))

            if size_value > best_size or (
                size_value == best_size and keyword_hits > best_keyword_hits
            ):
                best_size = size_value
                best_keyword_hits = keyword_hits
                best_magnet = magnet

        return best_magnet


def collect_magnets(directory: Path) -> Iterable[str]:
    for csv_path in sorted(directory.glob("*.csv")):
        best_magnet = pick_best_magnet(csv_path)
        if best_magnet:
            yield best_magnet


def write_output(directory: Path, magnets: Iterable[str]) -> int:
    output_path = directory / f"{directory.name}.txt"
    magnets = list(magnets)

    # 去重保持顺序，避免重复写入同一磁链
    unique_magnets: list[str] = []
    seen = set()
    for magnet in magnets:
        if magnet not in seen:
            unique_magnets.append(magnet)
            seen.add(magnet)

    if output_path.exists():
        existing = {
            line.strip()
            for line in output_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
    else:
        existing = set()

    new_entries = [magnet for magnet in unique_magnets if magnet not in existing]
    if not new_entries:
        return 0

    with output_path.open("a", encoding="utf-8") as handle:
        for magnet in new_entries:
            handle.write(f"{magnet}\n")

    return len(new_entries)


def process_directory(directory: Path) -> tuple[int, int]:
    magnets = list(collect_magnets(directory))
    if not magnets:
        return 0, 0
    added = write_output(directory, magnets)
    return added, len(magnets)


def find_target_directories(root: Path, recursive: bool) -> Sequence[Path]:
    if recursive:
        directories = {path.parent for path in root.rglob("*.csv")}
        if not directories and any(root.glob("*.csv")):
            directories.add(root)
        return sorted(directories)
    return [root] if any(root.glob("*.csv")) else []


def run(root: Path | str, *, current_only: bool = False) -> None:
    root_path = Path(root)

    if not root_path.exists():
        raise FileNotFoundError(f"未找到目录: {root_path}")
    if not root_path.is_dir():
        raise NotADirectoryError(f"指定路径不是目录: {root_path}")

    recursive = not current_only
    target_directories = find_target_directories(root_path, recursive)
    if not target_directories:
        if recursive:
            LOGGER.warning("未在该目录或子目录中找到任何 CSV 文件: %s", root_path)
        else:
            LOGGER.warning("目录中未找到 CSV 文件: %s", root_path)
        return

    if (
        recursive
        and root_path not in target_directories
        and any(root_path.glob("*.csv"))
    ):
        target_directories = [root_path, *target_directories]

    total_written = 0
    had_candidates = False

    for directory in target_directories:
        added, processed = process_directory(directory)
        output_path = directory / f"{directory.name}.txt"
        if processed == 0:
            LOGGER.info("%s 中没有符合条件的磁链。", directory)
            continue
        had_candidates = True
        if added > 0:
            total_written += added
            LOGGER.info("新增 %d 条磁链到 %s", added, output_path)
        else:
            LOGGER.info("%s 中的磁链已全部存在，未新增。", directory)

    if total_written == 0:
        if had_candidates:
            LOGGER.info("所有磁链均已存在，未新增。")
        else:
            LOGGER.warning("未写入任何磁链，请检查输入的 CSV 文件。")


def main() -> None:
    if not logging.getLogger().hasHandlers():
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
        )
    from utils import setup_daily_file_logger

    setup_daily_file_logger()
    args = parse_args()
    try:
        run(args.directory, current_only=args.current_only)
    except (FileNotFoundError, NotADirectoryError) as exc:
        LOGGER.error("%s", exc)
        raise SystemExit(str(exc))


if __name__ == "__main__":
    main()
