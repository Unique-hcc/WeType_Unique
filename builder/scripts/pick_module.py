#!/usr/bin/env python3
"""从模块仓库的最新 Release 里挑出「模块本体」APK。

模块仓库的 release 里可能同时挂着模块 APK（几 MB）和已经内置好的输入法整包（200 MB+），
所以默认按「体积最小的 .apk」来挑；要精确指定就用环境变量 MODULE_ASSET。

环境变量：
  MODULE_REPO   例：Unique-hcc/WeType_Unique
  MODULE_ASSET  可选，资产名精确/包含匹配
  GH_TOKEN      GitHub token，避免 API 限流

输出：tag / version / asset / url / size
"""
import json
import os
import re
import sys
import urllib.request

API = "https://api.github.com"


def get(url: str) -> dict:
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "wetype-patch-ci",
        **({"Authorization": f"Bearer {os.environ['GH_TOKEN']}"} if os.environ.get("GH_TOKEN") else {}),
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def main() -> None:
    repo = os.environ.get("MODULE_REPO", "").strip()
    if not repo:
        raise SystemExit("缺少 MODULE_REPO")

    release = get(f"{API}/repos/{repo}/releases/latest")
    tag = release.get("tag_name") or release.get("name") or ""
    assets = [a for a in release.get("assets", []) if a["name"].lower().endswith(".apk")]
    if not assets:
        raise SystemExit(f"{repo} 的最新 Release({tag}) 里没有 .apk 资产")

    want = os.environ.get("MODULE_ASSET", "").strip()
    if want:
        hit = [a for a in assets if a["name"] == want] or [a for a in assets if want in a["name"]]
        if not hit:
            raise SystemExit(f"未找到资产 {want}，可选：{[a['name'] for a in assets]}")
        picked = hit[0]
    else:
        picked = min(assets, key=lambda a: a["size"])

    # tag 形如 WeType_Unique_1.29.0 / v1.29.0，取最后一个版本号片段当模块版本
    found = re.findall(r"\d+(?:\.\d+)+", tag)
    version = found[-1] if found else (tag.lstrip("vV") or "unknown")
    pairs = {
        "tag": tag,
        "version": version,
        "asset": picked["name"],
        "url": picked["browser_download_url"],
        "size": str(picked["size"]),
    }
    for k, v in pairs.items():
        print(f"{k}={v}")
    print(f"candidates={[a['name'] for a in assets]}", file=sys.stderr)

    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            for k, v in pairs.items():
                f.write(f"{k}={v}\n")


if __name__ == "__main__":
    sys.exit(main())
