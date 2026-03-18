# 点收单识别 - Android APK 打包说明

Buildozer 只能在 **Linux** 下打包 Android。在 Windows 上请使用 **WSL2 + Ubuntu** 进行构建。

---

## 一、环境准备（Windows + WSL2）

### 1. 安装 WSL2 与 Ubuntu

在 **PowerShell（管理员）** 中执行：

```powershell
wsl --install -d Ubuntu
```

安装完成后重启，打开 **Ubuntu**，按提示创建用户名和密码。

### 2. 在 Ubuntu 中安装构建依赖

在 WSL 的 Ubuntu 终端中执行：

```bash
sudo apt update
sudo apt install -y \
  git zip unzip openjdk-17-jdk python3-pip python3-venv \
  autoconf libtool pkg-config zlib1g-dev \
  libncurses-dev cmake \
  libffi-dev libssl-dev
```

> **说明**：新版本 Ubuntu（如 24.04）已用 `libncurses-dev` 替代旧的 `libncurses5-dev`/`libtinfo5`，上述命令在 22.04 与 24.04 下均可使用。

### 3. 安装 Buildozer

Ubuntu 默认禁止用 `pip` 装到系统 Python（会报 `externally-managed-environment`），请用下面两种方式之一安装。

**方式一：用 pipx（推荐）**

```bash
sudo apt install -y pipx
pipx ensurepath
# 关闭并重新打开终端后执行，或先执行：source ~/.bashrc
pipx install buildozer
pipx inject buildozer setuptools cython
```

之后在任意目录可直接运行：`buildozer -v android debug`。

**方式二：用虚拟环境**

```bash
python3 -m venv ~/buildozer-venv
source ~/buildozer-venv/bin/activate
pip install --upgrade pip setuptools cython buildozer
```

> **说明**：  
> - 若报错 `No module named 'distutils'`，请先执行 `pip install setuptools`。  
> - 若报错 `Cython (cython) not found`，请执行 `pip install cython`。

以后每次打包前先激活环境再构建：

```bash
source ~/buildozer-venv/bin/activate
cd ~/ReceiptAPP
buildozer -v android debug
```

---

## 二、在 WSL 中构建 APK

**重要：不要在 Windows 盘符（如 `/mnt/c/...`）下构建**，否则可能因路径或权限问题失败。建议把项目复制到 WSL 家目录再构建。

### 1. 复制项目到 WSL

在 Ubuntu 终端中：

```bash
# 示例：从 Windows 项目路径复制到 WSL 家目录
cp -r /mnt/m/python/pro1/code2/ReceiptAPP ~/ReceiptAPP
cd ~/ReceiptAPP
```

请把 `/mnt/m/python/pro1/code2/ReceiptAPP` 换成你本机在 WSL 里看到的实际路径（在资源管理器里可能是 `M:\python\pro1\code2\ReceiptAPP`，在 WSL 里对应 `/mnt/m/...`）。

### 2. 首次构建（会下载 Android SDK/NDK，较慢）

**在 WSL 下建议用「干净 PATH」再构建**，避免 Windows 路径干扰导致 `C compiler cannot create executables`（见下方常见问题）。

```bash
cd ~/ReceiptAPP
# 仅用 Linux 路径，避免用到 Windows 下的编译器/工具
export PATH="$HOME/buildozer-venv/bin:/usr/bin:/bin:/usr/local/bin"
buildozer -v android debug
```

或直接使用项目里的脚本（会自动设置 PATH 并构建）：

```bash
cd ~/ReceiptAPP
chmod +x build_android_wsl.sh
./build_android_wsl.sh
```

若未用虚拟环境（用 pipx 安装的 buildozer），则：

```bash
cd ~/ReceiptAPP
export PATH="/usr/bin:/bin:/usr/local/bin:$HOME/.local/bin"
buildozer -v android debug
```

- 第一次会下载 Android SDK、NDK 等，可能需要 **20–40 分钟**，取决于网络。
- 完成后，APK 在项目目录下的 **`bin/`** 里，例如：  
  `~/ReceiptAPP/bin/receiptapp-0.1-arm64-v8a-debug.apk`

### 3. 后续仅改代码时的快速构建

```bash
cd ~/ReceiptAPP
export PATH="$HOME/buildozer-venv/bin:/usr/bin:/bin:/usr/local/bin"
buildozer -v android debug
```

---

## 三、安装到手机测试

### 方式一：拷贝 APK 到 Windows 再安装

1. 在 WSL 中把 APK 拷到 Windows 可访问的目录，例如：

   ```bash
   cp ~/ReceiptAPP/bin/*.apk /mnt/m/python/pro1/code2/ReceiptAPP/
   ```

2. 在 Windows 下用数据线把 APK 传到手机，或通过微信/QQ 发到手机，在手机上点击 APK 安装。

### 方式二：用 ADB 安装（需先装 Android 平台工具）

1. 在 Windows 上安装 [Android Platform Tools](https://developer.android.com/studio/releases/platform-tools)（或通过 Android Studio 安装）。
2. 手机开启「开发者选项」和「USB 调试」，用数据线连电脑。
3. 在 PowerShell 或 CMD 中：

   ```cmd
   adb install "M:\python\pro1\code2\ReceiptAPP\bin\receiptapp-0.1-arm64-v8a-debug.apk"
   ```

（路径按你实际 APK 位置修改。）

---

## 四、常见问题

| 现象 | 处理 |
|------|------|
| 在 `/mnt/c` 下构建报错 | 把项目复制到 WSL 家目录再构建，例如 `~/ReceiptAPP`。 |
| 找不到 `buildozer` | 用 `python3 -m buildozer`，或把 `~/.local/bin` 加入 PATH：`export PATH="$HOME/.local/bin:$PATH"`。 |
| **`C compiler cannot create executables`**（freetype 等 configure 报错） | 若已用干净 PATH 仍报错，多半是 freetype 的 configure 在交叉编译时于**主机上尝试运行 ARM 测试程序**导致（WSL 上常见）。**推荐改用 Docker 构建**（见下方「用 Docker 构建（WSL 失败时）」）；或在本机/云上使用纯 Linux 构建。 |
| 首次构建卡在下载 | 正常，SDK/NDK 体积大，多等一会；可检查网络/代理。 |
| 权限被拒绝 | 在 WSL 里对项目目录执行 `chmod -R u+w ~/ReceiptAPP`。 |
| 安装 APK 提示“无法安装” | 若是覆盖安装，先卸载旧版再装；或检查手机是否允许「未知来源」安装。 |

---

## 五、用 Docker 构建（WSL 下 freetype 失败时）

当 WSL 里已设置干净 PATH 仍出现 **C compiler cannot create executables**（freetype 阶段）时，是 python-for-android 在交叉编译时于主机上运行 ARM 测试程序导致的已知问题。**改用官方 Buildozer Docker 在容器内构建**可规避（容器内为纯 Linux 环境）。

**前提**：本机已安装 [Docker Desktop](https://www.docker.com/products/docker-desktop/)（Windows 或 WSL2 后端均可）。

### 在 WSL 里用 Docker 构建

```bash
# 进入项目目录（在 WSL 中的路径）
cd ~/ReceiptAPP

# 挂载项目 + 缓存，在容器内构建（首次会拉取镜像并下载 SDK/NDK，较慢）
docker run --interactive --tty --rm \
  --volume "$HOME/.buildozer":/home/user/.buildozer \
  --volume "$PWD":/home/user/hostcwd \
  --workdir /home/user/hostcwd \
  kivy/buildozer -v android debug
```

构建完成后，APK 仍在当前目录的 `bin/` 下（因项目目录已挂载进容器）。

### 在 Windows PowerShell 里用 Docker 构建

若在 Windows 下用 PowerShell 运行 Docker，且项目在 `M:\python\pro1\code2\ReceiptAPP`：

```powershell
cd M:\python\pro1\code2\ReceiptAPP
docker run --interactive --tty --rm `
  -v "${env:USERPROFILE}\.buildozer:/home/user/.buildozer" `
  -v "${PWD}:/home/user/hostcwd" `
  -w /home/user/hostcwd `
  kivy/buildozer -v android debug
```

（首次运行会下载 `kivy/buildozer` 镜像与 Android 构建依赖，耗时较长。）

---

## 六、构建产物说明

- **Debug APK**：`buildozer android debug` → `bin/receiptapp-0.1-arm64-v8a-debug.apk`，用于测试。
- **Release APK**（签名后上架）：需配置签名密钥，执行 `buildozer android release`，详见 [Buildozer 文档](https://buildozer.readthedocs.io/)。

按上述步骤即可在安卓端以 APK 形式运行并测试当前项目。若 WSL 下 freetype 报错无法解决，请优先使用 **Docker 构建**（第五节）。
