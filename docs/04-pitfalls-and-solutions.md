# 踩坑台账：本项目最宝贵的记录

> 本篇说明：这个项目踩过的每一个坑，格式统一为"现象 → 根因 → 解决方案/现状"。
> 新人接手时先看这里，能省掉大量重复排查时间。

---

## 坑 1：twikit 报 `Couldn't get KEY_BYTE indices`

**现象**：
在本机运行 twikit（任何版本），初始化时报错 `Couldn't get KEY_BYTE indices`，所有接口（`search_tweet` / `get_user_tweets` / `get_latest_timeline`）都无法使用。

**根因**：
X 后端为了防爬虫，要求每次请求带一个动态生成的 `transaction-id`（一串特殊的随机字符串）。twikit 通过解析 X 前端 JS 文件里的特定字节索引来生成这个值，但 X 已经修改了 JS 的格式，twikit 的正则表达式跟不上了，解析失败。**PyPI 最新版 2.3.3 和 GitHub 开发版都有这个问题**（正则相同），换版本解决不了。

**解决方案**：
服务器上用 `patch_twikit.py` 脚本直接修改 twikit 的 `transaction.py` 源文件（改 `ON_DEMAND` / `INDICES` 正则 + `get_indices` 函数），绕过 X 的反爬机制。这个补丁已持久应用在服务器 `C:\QuriovXTools\.venv` 里。

**本机能不能修**：理论上可以，但本机国内 IP 还有另一层问题（见坑 2），所以彻底放弃本机路线，全部走服务器。

---

## 坑 2：本机过不了 X 反爬——三种 IP 都不行

**现象**：
即使解决了 twikit 的 `KEY_BYTE` 问题，本机直接跑 twikit 访问 X 仍然失败。具体表现：
- **国内直连**：X 发 Arkose 挑战页（浏览器弹验证码，脚本拿不到数据）。
- **TUN 代理（美国数据中心 IP）**：X 影子屏蔽——返回 HTTP 200，但响应体是空的，不报错，静默失败。
- **更换 VPN 节点**：同样结果，X 对数据中心 / VPN IP 有专门的检测。

**根因**：
X 的反爬系统会识别 IP 类型。数据中心 IP（AWS / Azure / Cloudflare / VPN 提供商的 IP 段）被 X 拉黑或影子屏蔽。真实用户用的是住宅 IP，和数据中心 IP 的特征不同。

**解决方案**：
使用阿里云美国区的服务器（47.251.0.142）。阿里云的 IP 被 X 视为正常，通过了反爬检测。本机只负责 SSH 连接和结果处理，真正的 twikit 调用在服务器上执行。

---

## 坑 3：@Quriov 品牌号被 X 临时限读

**现象**：
x-research 搜索接口突然开始返回 404，但发推（x-publish）仍然正常。早上还能搜出 20 条，下午全 404，换关键词也一样。

**根因**：
当天测试时用 @Quriov 品牌官号高频执行搜索（批量测试），X 自动识别为异常行为，对该账号的搜索接口做了临时限制（写操作不受影响）。

**解决方案**：
- **短期**：等 X 自动解除限制（通常 1-3 天）。
- **根本**：别用品牌号高频自动搜索。搜索用小号，品牌号只用来发内容。用 `set_cookie.py --role search` 配一个搜索专用小号。

**教训**：搜索和发布要分账号，品牌号只发不搜。

---

## 坑 4：本机 Python 连 Google 崩（SSL: UNEXPECTED_EOF）

**现象**：
在 youtube-publish 开发时，用 `requests` 库或 `google-api-python-client` 调用 Google API，每次都报 `SSL: UNEXPECTED_EOF_WHILE_READING`。但用 `curl` 命令或 Python 标准库 `urllib` 请求同一个接口，完全正常。

**根因**：
本机网络层（TUN 代理 / 节点）对 requests/urllib3 的 SSL 握手有兼容问题，会提前关闭连接。标准库 urllib 的 SSL 实现走另一条路，不受影响。

**解决方案**：
youtube-publish 的 `oauth_setup.py` 和 `post_comment.py` 全部改写为纯 Python 标准库（`urllib`），不使用 `requests` / `google-api-python-client`。`requirements.txt` 清空（零第三方依赖）。

---

## 坑 5：YouTube OAuth 一串坑

这是好几个独立的坑，串联在一起让配置过程很痛苦，记录在这里防止重踩。

### 坑 5a：凭据在另一个 Google Cloud 项目里
**现象**：换账号重新授权时，去新的 Google Cloud 项目建凭据，怎么都授权失败。
**根因**：YouTube Data API v3 的启用、OAuth 同意屏幕、测试用户名单，全都绑在原来那个项目 `tidy-resolver-500509-j9`（应用名 `softskill`）。新项目没有这些配置。
**解决方案**：OAuth 相关操作统一在 `tidy-resolver-500509-j9` 这个项目下做，不要新建。

### 坑 5b：登录账号必须加进"测试用户"名单
**现象**：授权时浏览器报"此应用未经 Google 审核，无法授权"，无法继续。
**根因**：未提交 Google 审核的应用（我们自建的桌面应用）只能给"测试用户"名单里的账号授权。列表在 Google Cloud 的"OAuth 同意屏幕"设置里。
**解决方案**：在 `tidy-resolver-500509-j9` 项目的"OAuth 同意屏幕" → "测试用户"里，把要用来授权的 Google 账号邮箱加进去。

### 坑 5c：账号没有 YouTube 频道导致评论失败
**现象**：授权成功，跑 `post_comment.py --send`，调 API 报"无法找到频道"或"找不到资源"类错误。
**根因**：发评论的 API 要求以一个 YouTube 频道的身份发（即便是个人 Google 账号，也要先创建频道才有频道 ID）。账号本身没有创建 YouTube 频道，API 找不到发评论的身份。
**解决方案**：用要发评论的 Google 账号，去 YouTube 建一个频道（哪怕是空频道），之后 API 就能找到对应的频道 ID。

### 坑 5d：token.json 是自定义格式，不兼容 google 库
**现象**：换账号或 token 过期后，用标准的 google-auth 库无法读取已有的 `token.json`。
**根因**：我们用纯标准库实现 OAuth，生成的 `token.json` 格式是自定义的，不是 google-auth 库的格式。
**解决方案**：换账号或 token 失效时，删掉 `.secrets/token.json`，重新跑 `python scripts\oauth_setup.py --force` 重新走一遍授权流程。

---

## 坑 6：Reddit 账号用 Google 登录，没有密码

**现象**：想配置 reddit-publish，在 `.secrets/reddit.json` 填账号信息时，发现账号当初是用 Google 账号注册的，没有独立的 Reddit 密码，PRAW 的 script 模式无法登录。

**根因**：PRAW 的 script 应用模式（`grant_type=password`）要求直接用 Reddit 用户名 + 密码登录。用 Google / Apple 等第三方登录的账号，Reddit 没有给它分配密码，PRAW 无法使用这种方式认证。

**解决方案（未实施）**：
- 方案 A：给 Reddit 账号添加独立密码（Reddit 账号设置里，部分情况下能给已有的第三方登录账号加密码）。
- 方案 B：注册一个新的 Reddit 账号，直接用用户名+密码注册，不用第三方登录。
- 方案 C（备选）：改用基于浏览器 cookie 的方式绕过密码认证（PRAW 有实验性支持，但稳定性差）。

**当前状态**：暂缓，等账号问题解决后再测真发。

---

## 坑 7：ai-infohub 的 cookie 过期

**现象**：`C:\AIInfoHub\data\cookies.json` 里的 cookie 失效，twikit 报未登录或请求失败。

**根因**：X 的 cookie（`auth_token` / `ct0`）有效期有限，长时间不刷新会过期。ai-infohub 日报管线用的那份 cookie 是某个时间点手动导入的，没有自动刷新机制。

**解决方案**：
- 在服务器上用浏览器登录 X，重新导出 cookie，更新 `C:\AIInfoHub\data\cookies.json`（这是 ai-infohub 的 cookie，不要碰 `C:\QuriovXTools\cookies\`）。
- `C:\QuriovXTools\` 的 cookie 独立管理，用 `set_cookie.py` 工具从本机 Firefox 导出并同步到服务器。

**教训**：每个工具箱的 cookie 互相独立，别混用也别随便覆盖。

---

## 坑 8：本机操作含空格路径的问题

**现象**：本机项目路径含有空格和中文（`D:\Workspace\Quriov Team Work\...`），某些工具（如 curl 的 `-F @file` 参数）直接报错，找不到文件。

**根因**：curl 等 POSIX 工具对含空格 / 中文的路径有兼容问题，即使加了引号也可能失败。

**解决方案**：
- 含空格路径的文件操作优先用 Python 脚本（os / pathlib，对路径有完整支持）。
- 必要时用临时路径（不含空格），操作完再把结果搬回项目目录，临时路径清理。

---

## 坑 9：凭据安全——提交前核验

**为什么记这个**：这不是"坑"，而是一个重要的做法约定，记在这里提醒接手者。

在把 skill 推到 GitHub 之前，**必须**确认没有真实凭据被意外提交。核验命令：

```bash
git diff --cached | grep -iE "Autk86420|Autk24680|GOCSPX-|ya29\.|odyaccu01"
```

如果有输出（命中），说明凭据被意外加进了暂存区，立即取消这次提交并检查。

每个 skill 的 `.gitignore` 里都包含 `.secrets/` 目录，应该不会意外提交，但提交前再手动核验一次是好习惯。
