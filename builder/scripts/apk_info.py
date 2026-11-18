#!/usr/bin/env python3
"""从 APK 的二进制 AndroidManifest.xml 读取 package / versionCode / versionName。

不依赖 aapt / java，纯 Python 解析 AXML，便于在 CI 里直接跑。

这是**唯一可信的版本来源**：官方包文件名里的数字是内部构建号（wxkb_1422_32.apk
的 1422），真实 versionCode 是 59201，两者没有任何换算关系。

用法:
    python apk_info.py path/to/app.apk          # 打印 key=value
    python apk_info.py path/to/app.apk --json   # 打印 json
    GITHUB_OUTPUT=/path python apk_info.py ...  # 同时写入 GitHub Actions outputs
"""

from __future__ import annotations

import json
import os
import struct
import sys
import zipfile

RES_STRING_POOL = 0x0001
RES_XML_RESOURCE_MAP = 0x0180
RES_XML_START_ELEMENT = 0x0102
RES_XML_END_ELEMENT = 0x0103

ATTR_VERSION_CODE = 0x0101021B
ATTR_VERSION_NAME = 0x0101021C

TYPE_STRING = 0x03
TYPE_INT_DEC = 0x10
TYPE_INT_HEX = 0x11


def _parse_string_pool(data: bytes, off: int):
    header_size, size = struct.unpack_from("<HI", data, off + 2)
    count, style_count, flags, strings_start, styles_start = struct.unpack_from("<IIIII", data, off + 8)
    utf8 = bool(flags & 0x100)
    offsets = struct.unpack_from("<%dI" % count, data, off + header_size)
    base = off + strings_start
    out = []
    for o in offsets:
        p = base + o
        if utf8:
            # utf-16 length (1 or 2 bytes), then utf-8 length, then bytes
            n = data[p]
            p += 2 if n & 0x80 else 1
            n = data[p]
            if n & 0x80:
                n = ((n & 0x7F) << 8) | data[p + 1]
                p += 2
            else:
                p += 1
            out.append(data[p:p + n].decode("utf-8", "replace"))
        else:
            n = struct.unpack_from("<H", data, p)[0]
            p += 2
            if n & 0x8000:
                n = ((n & 0x7FFF) << 16) | struct.unpack_from("<H", data, p)[0]
                p += 2
            out.append(data[p:p + n * 2].decode("utf-16-le", "replace"))
    return out


def read_manifest_attrs(apk_path: str) -> dict:
    with zipfile.ZipFile(apk_path) as z:
        data = z.read("AndroidManifest.xml")

    str_type, header_size, total = struct.unpack_from("<HHI", data, 0)
    if str_type != 0x0003:
        raise ValueError("不是二进制 AndroidManifest.xml")

    strings: list[str] = []
    res_ids: list[int] = []
    off = header_size
    while off < total:
        ctype, chdr, csize = struct.unpack_from("<HHI", data, off)
        if csize <= 0:
            break
        if ctype == RES_STRING_POOL:
            strings = _parse_string_pool(data, off)
        elif ctype == RES_XML_RESOURCE_MAP:
            n = (csize - chdr) // 4
            res_ids = list(struct.unpack_from("<%dI" % n, data, off + chdr))
        elif ctype == RES_XML_START_ELEMENT:
            name_idx = struct.unpack_from("<I", data, off + chdr + 4)[0]
            tag = strings[name_idx] if name_idx < len(strings) else ""
            if tag == "manifest":
                attr_start, attr_size, attr_count = struct.unpack_from("<HHH", data, off + chdr + 8)
                base = off + chdr + attr_start
                result = {}
                for i in range(attr_count):
                    a = base + i * attr_size
                    _ns, aname, raw = struct.unpack_from("<III", data, a)
                    vtype = data[a + 15]
                    vdata = struct.unpack_from("<I", data, a + 16)[0]
                    rid = res_ids[aname] if aname < len(res_ids) else 0
                    key = None
                    if rid == ATTR_VERSION_CODE:
                        key = "versionCode"
                    elif rid == ATTR_VERSION_NAME:
                        key = "versionName"
                    elif rid == 0 and aname < len(strings) and strings[aname] == "package":
                        key = "package"
                    if key is None:
                        continue
                    if vtype == TYPE_STRING or (raw != 0xFFFFFFFF and vtype == TYPE_STRING):
                        result[key] = strings[vdata] if vdata < len(strings) else ""
                    elif vtype in (TYPE_INT_DEC, TYPE_INT_HEX):
                        result[key] = vdata
                    elif raw != 0xFFFFFFFF and raw < len(strings):
                        result[key] = strings[raw]
                    else:
                        result[key] = vdata
                return result
        off += csize
    raise ValueError("未在清单中找到 <manifest> 元素")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    info = read_manifest_attrs(sys.argv[1])
    vc = info.get("versionCode", "")
    vn = info.get("versionName", "")
    # 用户/系统设置里看到的完整版本：versionName 里已经带 versionCode 就不重复拼
    app_version = vn if (vc != "" and str(vc) in str(vn)) else (f"{vn}.{vc}" if vn else str(vc))
    pairs = {
        "package": info.get("package", ""),
        "versioncode": vc,
        "versionname": vn,
        "app_version": app_version,
    }
    if "--json" in sys.argv:
        print(json.dumps(pairs, ensure_ascii=False))
    else:
        for k, v in pairs.items():
            print(f"{k}={v}")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            for k, v in pairs.items():
                f.write(f"{k}={v}\n")


if __name__ == "__main__":
    main()
