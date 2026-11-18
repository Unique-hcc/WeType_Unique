# WeType × LSPatch 自动打补丁流水线

发一个模块 Release（或手动点一下、或每周一凌晨自动跑）→ 抓微信输入法**官网当前最新**安卓包 → 从 `Unique-hcc/WeType_Unique` 的**最新 Release** 取模块 → LSPatch 内置模块 + 补 `QUERY_ALL_PACKAGES` → 用 `Unique.bks` 重签名 → 产出 `微信输入法_<输入法完整版本>_V<模块版本>.apk`。

## 一、已实测跑通（2026-11-18 本机真实构建）

| 项目 | 结果 |
| --- | --- |
| 官方包 | `4.0.1` / versionCode **59201** / `wxkb_1422_32.apk`（1422 是构建号）/ 230.5 MB / 仅 arm64-v8a |
| 模块 | `WeType_Unique_1.29.0_release.apk` / 6.21 MB / 现代 libxposed 模块（`META-INF/xposed/*`） |
| 打补丁 | 成功，**耗时约 5 秒**（LSPatch 用嵌套 APK 方式，不重压原始包） |
| 产物 | 226 MB，`verified=true v2=true`，versionCode = 59201 |
| 签名 | 证书 SHA-256 `D7BD6F59…D555D21DFF`，与 `Unique.bks` 中 `unique` 条目完全一致 |
| 模块内置 | `assets/lspatch/modules/com.hcc.wetypeunique.apk` 已存在 |
| 权限 | `android.permission.QUERY_ALL_PACKAGES` 已写入 manifest |
| 名称 | manifest `application@label` = `微信输入法` |

> 坑 A：`keytool -printcert -jarfile` 会报 "Not a signed jar file"，因为 LSPatch 只做 v2/v3 签名、不做 v1 JAR 签名。校验必须用 apksig（`tools/VerifyApk.java` 就是干这个的，classpath 直接用 lspatch.jar，它内置了 apksig）。
>
> 坑 B：官方包名里的 `1422` **不是 versionCode**。真实 versionCode 是 `59201`（手机设置里看到的 `4.0.1.59201` = versionName + versionCode）。把 1422 当 versionCode 写进产物，安装会直接报「已安装更新的版本」（`INSTALL_FAILED_VERSION_DOWNGRADE`）。所以流水线改成下载后用 `scripts/apk_info.py` 直接读包内清单，不再猜文件名。

## 二、产出

- **Actions artifact 里的文件名**：`微信输入法_<输入法完整版本>_V<模块版本>.apk`，例 `微信输入法_4.0.1.59201_V1.29.0.apk`
  - 输入法版本 = 清单里的 versionName + "." + versionCode（动态，和手机设置里显示的一致）
  - 模块版本 = 模块仓库 release tag 里最后一个版本号片段（`WeType_Unique_1.29.0` → `1.29.0`）
- **Release 附件名**：`WeType_<输入法完整版本>_V<模块版本>.apk`（与 tag 同名）
  - 原因：GitHub 会把 asset 名里的中文直接吃掉，`微信输入法_4.0.1.59201_V1.29.0.apk` 上传后会变成 `_4.0.1.59201_V1.29.0.apk`。所以附件主动用 ASCII 名，下载后想改回中文名随便改，不影响安装。
- 桌面图标名：`微信输入法`（写在 APK 的 manifest label 里，和文件名无关）
- 内置内容：模块 APK、`QUERY_ALL_PACKAGES`、`-l 2` 签名绕过

## 三、目录（本目录位于 `WeType_Unique` 仓库的 `builder/` 下）

```
WeType_Unique/
├── README.md                          # 模块主页（不动）
├── LICENSE
├── .gitignore                         # 挡住 *.apk / *.bks / *.p12
├── .github/workflows/
│   └── wetype-patch.yml               # 流水线（必须在仓库根）
└── builder/
    ├── README.md                      # 本文件
    ├── .gitattributes
    ├── scripts/resolve_apk.py         # 官方最新版 + 直链（每次重新解析）
    ├── scripts/apk_info.py            # 读清单里的真实 package/versionCode/versionName
    ├── scripts/pick_module.py         # 模块仓库最新 release 挑包
    └── tools/
        ├── BksToP12.java              # BKS -> PKCS12
        └── VerifyApk.java             # apksig 校验签名 + 指纹比对
```

> **签名绝不进仓库**：`Unique.bks` 只以 base64 形式存在 GitHub Actions Secret 里，本地/CI 都是运行时还原成临时文件，且 `*.bks`、`*.p12`、`*.jks`、`*.keystore`、`*.b64` 全在 `.gitignore` 里。base64 也只是编码不是加密——Secret 泄露等于私钥泄露，别贴到 issue、commit message 或截图里。

## 四、两处关键实现

### 1. 版本永不写死

```
GET https://z.weixin.qq.com/android/download
→ 302 https://download.z.weixin.qq.com/app/android/<版本>/wxkb_<构建号>_<架构>.apk
```

官网发版只改 302 落点，脚本每次运行重新解析。备用：`WETYPE_DOWNLOAD_URL` 环境变量可直接指定直链兜底。

### 1.1 versionCode 必须从包内清单读，不能猜文件名

实测对照（同一台机器、同一个包）：

| 来源 | 值 | 正确性 |
| --- | --- | --- |
| 文件名 `wxkb_1422_32.apk` | `1422` | ✗ 内部构建号 |
| `AndroidManifest.xml` | `59201` | ✓ 真实 versionCode |
| versionName | `4.0.1` | ✓，手机里显示成 `4.0.1.59201` |

所以流程是：resolve（拿 URL）→ 下载 → **`apk_info.py` 读清单**（输出 `versioncode/versionname/app_version`）→ 用这个 versionCode 打补丁 → 校验步骤再读一次产物，和来源包比对，不一致直接 fail。

`apk_info.py` 是纯 Python 的 AXML 解析器（读 string pool + start element 属性 + resource map 判断 0x0101021b/0x0101021c），不依赖 aapt、不依赖 Java，CI 里零依赖。

### 2. BKS 必须转成 PKCS12

LSPatch 的 `KeystoreSpec.load()`：

```java
KeyStore keyStore = KeyStore.getInstance(KeyStore.getDefaultType());
```

JDK 21 上默认类型是 `PKCS12`；`Unique.bks` 是真 BKS v2（头 `00 00 00 02`、盐长 20、迭代 1993），直接喂进去必然失败。所以流水线先做无损转换：

```bash
javac -cp bcprov.jar -d tools/build tools/BksToP12.java
java -cp "bcprov.jar:tools/build" BksToP12 Unique.bks "<BKS密码>" unique sign.p12 "<p12密码>"
```

再用 `-k sign.p12 <p12密码> unique <p12密码>` 交给 LSPatch。PKCS12 的 store 密码与 key 密码必须一致，脚本按同一密码写入。

### 3. 拿到的是正式版，不是内测/灰度版

`https://z.weixin.qq.com/android/download` 是官网下载按钮背后的固定入口，返回的是**全量正式版**：

- 返回体是纯文本 `Found. Redirecting to https://download.z.weixin.qq.com/app/android/4.0.1/wxkb_1422_32.apk`
- 加 `?channel=beta`、`?channel=test`、`?beta=1` 之类的参数并不会切到别的包，302 依然指向**同一个正式版**（参数被忽略，没有渠道开关）
- 官网更新日志里带 `Beta` / `灰度` 字样的条目**只出现在 macOS 与 Windows**，安卓侧清一色是「正式发布」

所以这条链路拿不到安卓内测包。如果哪天腾讯开了安卓灰度，最可能的表现是「更新日志已公布新版本，但 302 落点还是旧版本」——脚本因此额外抓一次更新日志做交叉校验，两者不一致会打印：

```
warn: 更新日志最新安卓正式版是 X，下载落点是 Y（可能尚未全量放量 / CDN 未同步）
```

（输出里的 `changelog_version` 字段就是这个对照值，构建照旧用 302 的实际落点，保证打出来的包和下载到的一致。）

## 五、Secrets（3 个，只在仓库设置里，不进代码）

仓库页 → Settings → Secrets and variables → Actions → New repository secret：

| Secret | 值 |
| --- | --- |
| `KEYSTORE_B64` | `base64 -w0 Unique.bks` 的输出（整段，含换行也行） |
| `KEYSTORE_PASS` | BKS 口令（同时作为转换后 p12 的口令） |
| `KEY_ALIAS` | `unique` |

Windows 下生成 base64：Git Bash 里 `base64 -w0 "/d/HONOR Share/Honor Share/Unique.bks"`；或 `certutil -encode Unique.bks ks.b64`。**生成完把 `ks.b64` 删掉**，`.gitignore` 里已经挡住 `*.b64`。

GitHub 会在日志里自动掩码 Secret 内容，但反过来讲：Secret 一旦写进仓库文件、issue、commit message、截图，就等于私钥公开了。

## 六、触发

一共四种，产物命名和版本解析完全一致，区别只在于「谁来触发」和「发不发 Release」。

| 触发方式 | 何时 | 会自动发 Release 吗 |
| --- | --- | --- |
| **发布 Release**（上传新模块） | 你在本仓库点 Publish release 的那一刻 | ✅ 自动发，无需勾选 |
| 手动 Run workflow | 你自己点，可勾 `publish_release` | 看勾选（默认否） |
| issue 评论 `/build` | 手机最顺手，仅仓库所有者生效 | ❌ 只出 artifact |
| 定时 | 每周一 03:00（北京时间） | ❌ 只出 artifact；**版本没变直接跳过** |

**手动 Run workflow 的参数**：

- `module_asset`：指定 Release 资产名（留空自动取体积最小的 .apk）
- `version_code_bump`：versionCode 加值（同版本覆盖安装时用）
- `force`：跳过缓存重下官方包
- `publish_release`：默认关。勾了才会在构建成功后建 Release 并上传产物

**关于定时任务的去重**：每次成功构建后会把 `<输入法版本>.<构建号>_V<模块版本>` 记进 Actions cache（`.state/last.txt`）。下一次定时跑时先比对，完全一致就直接跳过下载和打包，整个 job 十几秒结束并标绿，摘要里写「跳过：版本未变化」。只要输入法版本或模块版本任一变化，就正常打包。手动 / Release / `/build` 触发不受此限制，随时能强制重打。

**Release 触发的防循环**：流水线自己发的 Release 会在 notes 里写入 `auto-generated by wetype-patch` 标记，`release: published` 再次触发时 job 直接跳过，不会「发版→触发→再发版」。

**注意**：Release 触发认的是「发布 Release」这个动作，`git push` 代码不会触发。所以模块更新后要真的去发一个 Release（草稿点 Publish 才算）。

## 七、模块包的挑选规则

本仓库的 release 同时挂着两个 apk：`4.0.1_V1.29.0.apk`（226 MB 已内置整包）和 `WeType_Unique_1.29.0_release.apk`（6.21 MB 模块本体）。脚本默认取**体积最小的 `.apk`**，正好命中模块；要精确指定就用 `module_asset` 填资产名。

## 八、权限：只有仓库所有者能触发

- **手动 Run workflow**：需要仓库 write 权限。public 仓库的陌生访客看不到这个按钮，fork 也不会带过去。
- **issue 评论 `/build`**：job 上有 `github.event.comment.user.login == github.repository_owner` 的硬校验，别人评论同样内容只会得到 skipped。
- **Release 触发**：能发 Release 的人本身就必须有 write 权限。
- **定时**：仓库自己的 schedule，与人为操作无关。
- 产物（artifact / Release）下载同样要登录且有读权限。

也就是说：**别人既不能替你跑打包，也拿不到你的产物**。

## 九、必须知道的坑

1. **换签名 = 先卸官方版**，本地词库/设置会清空。versionCode 现在与官方完全一致（59201），所以「已安装更新的版本」不会再出现；但签名不同，不卸载仍然会报 `INSTALL_FAILED_UPDATE_INCOMPATIBLE`（签名不一致）——必须先卸。`version_code_bump` 只在需要覆盖安装自己的旧产物时用。
2. **微信生态的签名校验大概率会挂**：登录、多端同步、剪贴板互传走 openSDK 签名校验，换签名后很可能不可用。
3. **输入法身份**：IME 需被系统列入输入法列表，部分国内 ROM 校验签名/来源。
4. **腾讯系可能有完整性校验**：闪退把 `-l` 从 2 提到 3，或加 `--debuggable` 看日志。
5. **别把 230MB 官方包入库**（GitHub 单文件 100MB 限制 + 二次分发问题），流水线用 Actions cache 缓存。
6. **Release 是自动发的，artifact 只有 2 天**：日常取包去 Releases（`WeType_<版本>_V<模块版本>`，签名说明写在 notes 里）。artifact 只是副产物，`retention-days: 2` 到期即删。本仓库是 public，Release 等于公开分发「腾讯官方包 + 模块内置」的二次打包版本，自己判断风险；不想公开发就把这套流水线挪到 private 仓库。
7. **`QUERY_ALL_PACKAGES` 是敏感权限**：只自己装，别分发；Android 11+ 才生效。
8. **模块要跟版本走**：输入法升级后资源 id / 类名会漂。
9. **本机删掉 `Unique.bks` 不影响 CI**：云上用的是仓库 Secret 里那份 base64，和你电脑无关。但 Secret 是只写不可读的，本地文件删了 + 密码忘了 = 再也签不出能覆盖安装的包，务必离线备份两份（U 盘 + 私有网盘），密码单独记。
10. **定时任务用的是 GitHub cron（UTC）**：`0 19 * * 0` 才是北京时间周一 03:00。写成 `0 3 * * 1` 会变成周一 11:00。定时在高峰期可能延迟几分钟到几十分钟，属正常。
11. **流水线自己发的 Release 不会污染模块来源**：它的 tag 形如 `WeType_4.0.1.59201_V1.29.0`、notes 里带 `auto-generated by wetype-patch`，`pick_module.py` 双判据剔除后再取你的模块 Release。之前踩过一次：没剔除时 `/releases/latest` 拿到 226MB 成品整包当模块喂给 LSPatch，日志只打一行 `module.apk ... not a valid apk` 就继续，产物 versionCode 全对但 `assets/lspatch/modules/` 是空的。现在 Patch 步骤会 grep 日志，出这句直接失败。

## 十、落地顺序

1. 文件已在仓库里（`builder/` + `.github/workflows/wetype-patch.yml`），push 到 `main`。
2. 按第五节配 3 个 Secret。
3. Actions 里手动 Run 一次，确认 `Verify content` 与 `Verify signature` 都通过。
4. 下载 artifact 装机，先卸官方版再装。

## 十一、报错对照

| 报错 | 原因 | 处理 |
| --- | --- | --- |
| `java.io.EOFException`（`Convert keystore` 步） | 三个 Secret 全空 → `official.bks` 是 0 字节 | 按第五节添加 Secret；现在流水线会先检查并直接报「缺少 Secret」 |
| `文件头不是 BKS v2 的 00 00 00 02` | 贴进去的不是 BKS 的裸 base64（常见：`certutil` 带 BEGIN/END 头、贴成了 p12 或 jks） | 用 `base64 -w0 Unique.bks` 的输出整段粘贴 |
| `解出来只有 N 字节` | base64 被截断 / 只贴了一部分 | 重新复制完整内容，GitHub 输入框支持长文本 |
| `KeyStore integrity check failed` | `KEYSTORE_PASS` 不对 | 换成 BKS 真实口令（不是 p12 的） |
| `Cannot recover key` / `alias 不存在` | `KEY_ALIAS` 不对 | `keytool -list -keystore Unique.bks -storetype BKS -providerclass org.bouncycastle.jce.provider.BouncyCastleProvider -providerpath bcprov.jar` 看真实别名 |
| Secret 明明加了却还是空 | 加在了 Variables 页签 / Environment secret / 名字大小写不一致 | 必须在 **Secrets** 页签，仓库级，`KEYSTORE_B64` 等大小写完全一致 |
