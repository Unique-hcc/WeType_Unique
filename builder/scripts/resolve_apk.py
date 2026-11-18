#!/usr/bin/env python3
"""解析微信输入法「官方当前最新」安卓包，不写死任何版本号。

原理（2026-11-18 实测）：
  GET https://z.weixin.qq.com/android/download
  -> 302 Location: https://download.z.weixin.qq.com/app/android/<版本>/wxkb_<构建号>_<架构>.apk

官网每次发版只改这个 302 的落点，所以每次运行都重新解析，天然跟着最新版走。
若官网入口哪天变了，可用环境变量 WETYPE_DOWNLOAD_URL 直接指定直链兜底。

⚠️ 文件名里的数字（如 wxkb_1422_32.apk 的 1422）是**内部构建号**，不是 versionCode。
真实 versionCode 只能从 APK 的 AndroidManifest.xml 读（实测 4.0.1 = 59201）。
把构建号当 versionCode 写进重打包产物，安装时会被系统判成降级
（INSTALL_FAILED_VERSION_DOWNGRADE，提示「已安装更新的版本」）。

输出（同时写入 GITHUB_OUTPUT）：version / build / filename / url / changelog_version
真实 versionCode / versionName 由 scripts/apk_info.py 在下载之后解析。
"""
import os
import re
import sys
import time
import urllib.error
import urllib.request

UA = ("Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36")
ENDPOINT = "https://z.weixin.qq.com/android/download"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, msg, headers, fp)


def resolve_location(url: str, retries: int = 4) -> str:
    opener = urllib.request.build_opener(_NoRedirect)
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            opener.open(req, timeout=30)
            raise SystemExit("接口未返回 302，官网下载入口可能已变更")
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307, 308):
                loc = e.headers.get("Location")
                if loc:
                    return loc
            last = e
        except SystemExit:
            raise
        except Exception as e:  # noqa: BLE001
            last = e
        time.sleep(2 ** i)
    raise SystemExit(f"解析直链失败: {last}")


def latest_changelog_android() -> str:
    """官网更新日志里最新的「for Android 正式发布」版本，用来交叉校验。

    注意：更新日志里带 Beta / 灰度 字样的条目只出现在 macOS 和 Windows，
    安卓侧全部是「正式发布」——官网没有安卓内测入口。
    """
    try:
        req = urllib.request.Request("https://z.weixin.qq.com/",
                                     headers={"User-Agent": UA})
        html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
        vers = re.findall(r"微信输入法\s*([0-9]+(?:\.[0-9]+)+)\s*for\s*Android\s*正式发布", html)
        if not vers:
            return ""
        return max(vers, key=lambda v: tuple(int(x) for x in v.split(".")))
    except Exception:  # noqa: BLE001
        return ""


def main() -> None:
    override = os.environ.get("WETYPE_DOWNLOAD_URL", "").strip()
    location = override or resolve_location(ENDPOINT)

    m = re.search(r"/app/android/([0-9][0-9.]*)/([A-Za-z0-9_.\-]+\.apk)", location)
    if m:
        version, filename = m.group(1), m.group(2)
    else:
        filename = os.path.basename(location.split("?")[0])
        vm = re.search(r"(\d+\.\d+(?:\.\d+)*)", filename)
        version = vm.group(1) if vm else "unknown"

    build = ""
    cm = re.search(r"_(\d+)(?:_\d+)?\.apk$", filename)
    if cm:
        build = cm.group(1)

    pairs = {
        "version": version,
        "build": build,
        "filename": filename,
        "url": location,
        "changelog_version": latest_changelog_android(),
    }
    for k, v in pairs.items():
        print(f"{k}={v}")
    ga = pairs["changelog_version"]
    if ga and ga != version:
        print(f"warn: 更新日志最新安卓正式版是 {ga}，下载落点是 {version}"
              f"（可能尚未全量放量 / CDN 未同步）", file=sys.stderr)
    print("note: 文件名里的 %s 是构建号，versionCode 由 apk_info.py 从清单读取" % (build or "数字"),
          file=sys.stderr)

    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            for k, v in pairs.items():
                f.write(f"{k}={v}\n")


if __name__ == "__main__":
    sys.exit(main())
