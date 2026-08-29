# GitHub 云端打包 macOS 版 · 操作说明

> 思路:GitHub 提供免费的 macOS 云服务器(真实苹果硬件,合法),
> 我们把打包命令做成自动化流程(.github/workflows/build-macos.yml),
> 你只负责"上传代码 → 等 10 分钟 → 下载成品"。

## 第一次使用(约 15 分钟)

### 第 1 步:注册 GitHub

1. 打开 https://github.com/signup 注册账号(免费,邮箱验证即可);
2. 登录后点右上角 **+ → New repository**:
   - Repository name 填:`macos-pack`(或其他任意名字)
   - 选 **Public(公开)** ← 关键:公开仓库的 macOS 云跑器**完全免费**,私有仓库会消耗付费额度
   - 其他保持默认,点 **Create repository**

### 第 2 步:上传文件

1. 在刚建好的仓库页面点 **Add file → Upload files**;
2. 把本文件夹先解压到本地,然后把 **`.github` 文件夹、`mycloud_gui.py`、`mycloud_download.py` 一起拖进上传区**
   (GitHub 上传支持拖文件夹,`.github` 是普通文件夹名,拖进去就会保留目录结构);
3. 点 **Commit changes**。上传完成即自动触发打包,无需任何其他操作。

### 第 3 步:下载成品

1. 仓库顶部的 **Actions** 标签页,能看到"构建 macOS 版云盘下载器"正在跑;
2. 约 10 分钟(Intel 和 Apple Silicon 各 1 个,共 2 个任务)后变绿 ✅;
3. 点进对应任务 → 底部 **Artifacts** → 各自下载:
   - `云盘下载器-intel`:给 Intel 芯片 Mac
   - `云盘下载器-arm64`:给 Apple Silicon 芯片 Mac(M 系列)
4. 解压得到 `云盘下载器.dmg` 或 `云盘下载器.app`:
   - 双击挂载 dmg,把 app 拖到"应用程序"文件夹;
   - 首次打开遇到"无法验证开发者":**右键 → 打开 → 再点打开**即可;
   - 若嫌归档包里面的 .app 没执行权限,在终端执行一次 `xattr -dr com.apple.quarantine 云盘下载器.app` 即可。

## 以后更新版本

直接改同目录的 `mycloud_gui.py`/`mycloud_download.py` 重新上传(或点 **Edit** 修改),
push 会再次自动打包,10 分钟后又可下载新成品。(也可以点 Actions → 工作流 → **Run workflow** 手动重新跑。)

## 常见问题

- **Actions 没自动跑**:检查文件路径是否严格为 `.github/workflows/build-macos.yml`(大小写、目录层级);
  也可以在 Actions 标签页里点 **Run workflow** 手动触发。
- **任务失败**:点进失败任务查看红色日志。最常见的是 PyInstaller 报错,把日志截图/贴给我即可。
- **国内访问 GitHub 慢**:仓库/网页下载可用加速镜像(如 fastgit、ghproxy),或挂代理;上传建议用网页拖拽。
- **隐私**:公开仓库仅暴露这几行代码(无密钥、无账号信息),只会被 GitHub 自动打包,没有其他人需要关心。
- **不想要公开仓库**:私有仓库也能用,但每月免费额度按 10 倍消耗(macOS 跑器),约合 200 分钟/月,够用 13 次打包。

## 文件说明

| 文件 | 作用 |
|---|---|
| `mycloud_download.py` / `mycloud_gui.py` | 下载器源码(跨平台,与 Windows 版同一套) |
| `.github/workflows/build-macos.yml` | GitHub 自动打包流程(Intel + Apple Silicon 双版本) |

打包命令与配套说明(`一键打包.command` 等)在 Windows 本目录的 `macOS版` 文件夹里,需要在本机 Mac 上手动打包时用;GitHub 方案则完全不需要。
