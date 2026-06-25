这个说明对应 skill 的 .secrets/ 文件夹（敏感凭据目录，已被 .gitignore 挡住，绝不会进 git、不会同步给团队其他人）。
每个使用者必须各自在自己机器上、在 skill 的 .secrets/ 文件夹里准备下面两个文件。

==================================================================
需要放进 .secrets/ 的两个文件
==================================================================

1) client_secret.json   （OAuth 客户端凭据，从 Google Cloud 下载）
   ----------------------------------------------------------------
   - 去 Google Cloud Console（读侧 youtube-research 已经启用过 YouTube Data API v3 的那个项目即可）。
   - 左侧「API 和服务」→「凭据」→「创建凭据」→「OAuth 客户端 ID」。
   - 应用类型选「桌面应用 (Desktop app)」，名字随便起（如 youtube-publish）。
   - 创建后点「下载 JSON」，下载下来的文件**改名为 client_secret.json**，放到 .secrets/ 文件夹。
   - 文件内容大致长这样（这是格式示例，不是真凭据）：
       {"installed":{"client_id":"xxx.apps.googleusercontent.com",
        "project_id":"...","auth_uri":"...","token_uri":"...",
        "client_secret":"...","redirect_uris":["http://localhost"]}}

2) token.json           （授权后自动生成，不用手动建）
   ----------------------------------------------------------------
   - 不要手动创建。
   - 跑一次 `python scripts/oauth_setup.py`，浏览器会弹出让你用 Google 账号登录授权，
     授权成功后脚本会自动在 .secrets/ 里生成 token.json（含 refresh_token，可自动续期）。
   - 之后 post_comment.py 会自动读取并刷新它，一般不用再管。

==================================================================
安全须知
==================================================================
- 这两个文件都是私有凭据，绝不能进 git、不能发给别人、不能贴聊天。
- token.json 等于「以你的 Google 账号身份发评论」的钥匙，丢了要立刻去
  Google 账号「第三方应用访问权限」里撤销授权。
- 若不慎泄露 client_secret.json，去 Google Cloud 凭据页删掉该 OAuth 客户端重建。
