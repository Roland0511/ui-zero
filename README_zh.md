# UI-Zero

[English](https://github.com/Roland0511/ui-zero#readme) | **中文**

一个基于AI的UI自动化测试Python库。该库提供命令行工具，使用计算机视觉和AI模型进行自动化UI测试。

## 特性

- 通过ADB进行Android设备自动化
- AI驱动的UI元素识别和交互
- 命令行界面用于测试执行
- 支持多种AI模型（豆包、Ark等）
- 完整的截图和交互功能
- **国际化支持** - 自动检测系统语言，支持中英文界面
- **标准化本地化** - 使用gettext进行专业的国际化管理

## 安装

使用uv（推荐）：
```bash
uv add ui-zero
```

或使用pip：
```bash
pip install ui-zero
```

## 开发环境安装

```bash
# 克隆仓库
git clone https://github.com/Roland0511/ui-zero.git
cd ui-zero

# 使用uv安装开发依赖
uv sync --dev

# 或使用pip
pip install -e ".[dev]"
```

## 设置环境变量

本库使用字节跳动的[UI-TARS](https://github.com/bytedance/UI-TARS)模型进行AI驱动的UI识别。
按照[部署指南](https://bytedance.sg.larkoffice.com/docx/TCcudYwyIox5vyxiSDLlgIsTgWf)部署模型并获取API密钥。

完成后，在你的环境中设置以下变量：
```bash
export OPENAI_API_KEY="your_api_key_here"
export OPENAI_BASE_URL="your_api_base_url_here"
```

## 环境要求

### 计算机要求
- Python 3.10+
- 安装了ADB的Android SDK
- 连接的Android设备，已启用USB调试

### Android设备要求
- Android 8.0+（API级别26+）
- 已启用USB调试
- 已安装[ADBKeyboard](https://github.com/senzhk/ADBKeyBoard)，用于文本输入支持

## 命令行使用

安装后，可以使用`uiz`命令：

```bash
# 使用测试用例文件运行
uiz --testcase test_case.json

# 使用直接命令运行
uiz --command "找到设置图标并点击"

# 列出可用设备
uiz --list-devices

# 使用特定设备（连接多个设备时推荐）
uiz --device DEVICE_ID --command "找到设置图标并点击"

# 启用调试模式
uiz --debug --command "搜索Wi-Fi设置，然后点击"

# 禁用历史记录功能
uiz --no-history --command "打开应用"

# 查看帮助信息
uiz --help
```

## Python API使用

```python
from ui_zero import AndroidAgent, ADBTool

# 初始化ADB和agent
adb_tool = ADBTool()
agent = AndroidAgent(adb_tool)

# 运行测试步骤
result = agent.run("找到搜索栏并输入'hello world'")

# 带回调函数的执行
def on_screenshot(img_bytes):
    print(f"截图大小: {len(img_bytes)} bytes")

def on_action(prompt, action):
    print(f"执行动作: {action.action}")

result = agent.run(
    "点击设置按钮",
    screenshot_callback=on_screenshot,
    preaction_callback=on_action
)
```

## 国际化功能

UI-Zero支持基于系统语言的自动本地化：

### 自动语言检测
系统会自动检测以下环境变量并设置相应语言：
- `LANG`
- `LC_ALL` 
- `LC_MESSAGES`

### 手动设置语言
```python
from ui_zero.localization import set_language

# 设置为中文
set_language('zh_CN')

# 设置为英文  
set_language('en_US')
```

### 支持的语言
- 中文（简体）：`zh_CN`
- 英文（美式）：`en_US`

## 开发指南

### 代码质量检查

```bash
# 代码格式化
uv run black ui_zero/

# 导入排序
uv run isort ui_zero/

# 类型检查
uv run mypy ui_zero/

# 代码检查
uv run flake8 ui_zero/
```

### 运行测试

```bash
# 运行所有测试
uv run pytest

# 运行带覆盖率的测试
uv run pytest --cov=ui_zero

# 运行本地化测试
uv run pytest tests/test_localization.py -v
```

### 翻译管理

编译翻译文件：
```bash
# 编译所有.po文件为.mo文件
uv run python scripts/compile_translations.py
```

手动测试本地化：
```bash
# 运行本地化手动测试
uv run python tests/test_localization.py --manual
```

## 项目结构

```
ui_zero/
├── __init__.py           # 包初始化
├── cli.py               # 命令行界面
├── agent.py             # Android自动化代理
├── adb.py               # ADB工具类
├── localization.py      # 国际化管理
├── locale/              # 翻译文件目录
│   ├── messages.pot     # 翻译模板
│   ├── zh_CN/LC_MESSAGES/
│   │   ├── ui_zero.po   # 中文翻译源文件
│   │   └── ui_zero.mo   # 中文二进制文件
│   └── en_US/LC_MESSAGES/
│       ├── ui_zero.po   # 英文翻译源文件
│       └── ui_zero.mo   # 英文二进制文件
└── models/              # AI模型集成
    ├── __init__.py
    ├── arkmodel.py      # Ark模型基类
    └── doubao_ui_tars.py # 豆包UI-TARS模型
```

## 测试用例格式

### JSON格式
创建`test_case.json`文件：

```json
[
    "找到设置图标并点击",
    "滚动到底部",
    "点击关于手机",
    "返回上一页"
]
```

### YAML格式（推荐）
创建`test_case.yaml`文件以支持更高级的测试场景：

```yaml
android:
  # 设备 ID，可选，默认使用第一个连接的设备
  deviceId: <device-id>
tasks:
  - name: <任务名称>
    continueOnError: <boolean> # 可选，错误时是否继续执行下一个任务，默认 false
    flow:
      # 执行一个交互，`ai` 是 `aiAction` 的简写方式
      - ai: <prompt>

      # 这种用法与 `ai` 相同
      - aiAction: <prompt>

      # 等待某个条件满足，并设置超时时间(ms，可选，默认 30000)
      - aiWaitFor: <prompt>
        timeout: <ms>

      # 执行一个断言
      - aiAssert: <prompt>
        errorMessage: <error-message> # 可选，当断言失败时打印的错误信息

      # 等待一定时间（毫秒）
      - sleep: <ms>

  - name: <另一个任务名称>
    flow:
      # ...
```

完整示例请参考项目根目录下的 [`test_case.example.yaml`](test_case.example.yaml) 文件。

## 环境变量

| 变量名 | 描述 | 示例 |
|--------|------|------|
| `ARK_API_KEY` | UI-TARS模型API密钥 | `your_api_key_here` |
| `OPENAI_API_KEY` | OpenAI兼容API密钥 | `sk-...` |
| `OPENAI_BASE_URL` | OpenAI兼容API基础URL | `https://api.openai.com/v1` |
| `LANG` | 系统语言（自动检测） | `zh_CN.UTF-8` |

## 故障排除

### 常见问题

1. **ADB命令不可用**
   ```bash
   # 确保Android SDK已安装并添加到PATH
   export PATH=$PATH:$ANDROID_HOME/platform-tools
   ```

2. **设备连接问题**
   ```bash
   # 检查设备连接
   adb devices
   
   # 重启ADB服务
   adb kill-server && adb start-server
   ```

3. **检测到多个设备**
   - 当连接多个设备时，工具会自动选择第一个设备
   - 使用 `--device DEVICE_ID` 指定特定设备以避免歧义
   - 使用 `--list-devices` 查看所有可用设备

4. **API密钥问题**
   ```bash
   # 确保环境变量已设置
   echo $ARK_API_KEY
   ```

5. **文本输入问题**
   - 确保设备已安装ADBKeyboard应用
   - 在设备设置中启用ADBKeyboard作为输入法

## 贡献

欢迎贡献！请查看[贡献指南](CONTRIBUTING.md)了解详情。

## 许可证

MIT License - 查看[LICENSE](LICENSE)文件了解详情。

## 支持

- 问题报告：[GitHub Issues](https://github.com/Roland0511/ui-zero/issues)
- 文档：[项目文档](https://github.com/Roland0511/ui-zero#readme)
- 仓库：[GitHub](https://github.com/Roland0511/ui-zero)