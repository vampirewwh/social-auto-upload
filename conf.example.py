from pathlib import Path
import os

BASE_DIR = Path(__file__).parent.resolve()

# 数据目录：账号 cookie、数据库、素材、日志都放这里，便于换盘或备份。
# 优先级：环境变量 SAU_DATA_DIR > 项目根的 data_dir.txt > 项目根目录
_DATA_DIR_FILE = BASE_DIR / "data_dir.txt"


def _resolve_data_dir() -> Path:
    env = (os.environ.get("SAU_DATA_DIR") or "").strip()
    if env:
        return Path(env).expanduser().resolve()
    try:
        raw = _DATA_DIR_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        raw = ""
    if raw:
        return Path(raw).expanduser().resolve()
    return BASE_DIR


DATA_DIR = _resolve_data_dir()


def data_path(*parts: str) -> Path:
    """数据目录下的路径，例如 data_path("cookies", "douyin_a.json")。"""
    return DATA_DIR.joinpath(*parts)


def set_data_dir(path: str) -> None:
    """写入 data_dir.txt；调用方需要重启服务才会生效。"""
    target = Path(path).expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)
    _DATA_DIR_FILE.write_text(str(target), encoding="utf-8")


def ensure_data_dirs() -> None:
    for name in ("cookies", "db", "videos", "logs"):
        data_path(name).mkdir(parents=True, exist_ok=True)


XHS_SERVER = "http://127.0.0.1:11901"  # only used by xhs-related flows
LOCAL_CHROME_PATH = ""  # optional, e.g. C:/Program Files/Google/Chrome/Application/chrome.exe
LOCAL_CHROME_HEADLESS = True  # default headless behavior for uploader/examples
DEBUG_MODE = True  # default debug behavior
# Optional proxy for the YouTube uploader. Where youtube.com is blocked, direct
# connections time out and the (patchright) chromium does NOT use the system proxy.
# Point this at your local proxy port, e.g. "http://127.0.0.1:7890". None = no proxy.
YT_PROXY = None
