# WorkBuddy 离线发布包

从项目根目录运行：

```sh
python3 -B tools/workbuddy/package.py --version 0.2.2 ~/Desktop/mem-sharing-workbuddy-0.2.2.zip
```

打包机需要 GitHub 网络访问。脚本读取 memSharing 当前 Git 提交中的核心文件，并浅获取 Context Keeper 官方 `main`。内层 `assets/runtime.zip` 保留核心目录结构与上游 Git 对象。外层 WorkBuddy ZIP 仅有根目录与 `assets/` 一层，并附带最终文件的 SHA-256 清单。通过开放平台手动上传 ZIP，头像可从同一包的 `assets/icon.png` 取出。

通过 GitHub 仓库安装 memSharing 时，用户选装 Context Keeper 后由常规安装器在线获取其官方 `main`。WorkBuddy 打包用的上游检出放在临时目录，源码快照仅进入离线 ZIP，ZIP 输出到仓库外。

安装入口为包根目录的 `offline.py`。它使用包内文件备齐安装来源，再交给原有安装器生成执行计划。用户单独选择安装 Context Keeper 后，使用包内快照建立或复用独立源码目录，安装器仍需要真实批准。现有独立目录若有修改或提交不同，离线入口会保留现场并报出路径。WorkBuddy 的发布版本独立于 memSharing 核心版本。
