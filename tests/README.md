# UI-Zero 测试套件

本目录包含UI-Zero项目的单元测试和集成测试。

## 测试文件结构

- `test_localization.py` - 本地化功能测试
- `test_cli.py` - CLI模块单元测试
- `test_cli_integration.py` - CLI模块集成测试

## 运行测试

### 运行所有测试
```bash
uv run python -m pytest tests/ -v
```

### 运行特定测试文件
```bash
# 运行CLI单元测试
uv run python -m pytest tests/test_cli.py -v

# 运行CLI集成测试
uv run python -m pytest tests/test_cli_integration.py -v

# 运行本地化测试
uv run python -m pytest tests/test_localization.py -v
```

### 运行特定测试类
```bash
uv run python -m pytest tests/test_cli.py::TestYamlToTestcases -v
```

### 运行特定测试方法
```bash
uv run python -m pytest tests/test_cli.py::TestYamlToTestcases::test_convert_yaml_to_testcases_basic -v
```

### 运行带覆盖率的测试
```bash
uv run python -m pytest tests/test_cli.py --cov=ui_zero.cli --cov-report=term-missing
```

## CLI模块测试覆盖范围

### 单元测试 (`test_cli.py`)

#### TestDeviceListing
- ✅ 成功获取设备列表
- ✅ 获取设备列表失败处理

#### TestFileLoading
- ✅ 成功加载JSON测试用例文件
- ✅ 处理不存在的文件
- ✅ 处理无效JSON文件
- ✅ 处理格式错误的JSON文件
- ✅ 成功加载YAML配置文件
- ✅ 处理不存在的YAML文件
- ✅ 处理无效YAML文件
- ✅ 处理格式错误的YAML文件

#### TestYamlToTestcases
- ✅ 基本的YAML转换
- ✅ continueOnError参数处理
- ✅ 无设备ID的情况
- ✅ 缺少tasks字段的错误处理
- ✅ 无效tasks字段的错误处理
- ✅ 空tasks列表处理
- ✅ 无效任务格式处理

#### TestActionExecution
- ✅ 等待动作执行
- ✅ 默认任务名处理

#### TestUnifiedActionExecution
- ✅ CLI模式下的等待动作执行
- ✅ GUI模式下的等待动作执行
- ✅ 等待动作的默认时长
- ✅ CLI模式下的AI动作执行
- ✅ GUI模式下的AI动作执行
- ✅ 未知动作类型处理

#### TestTestRunner
- ✅ TestRunner初始化
- ✅ 成功执行步骤
- ✅ 带回调的步骤执行
- ✅ 步骤执行异常处理

#### TestRunTestcases
- ✅ CLI模式下的测试用例执行
- ✅ continueOnError功能
- ✅ 遇到错误时停止执行
- ✅ 键盘中断处理

#### TestExecuteSingleStep
- ✅ 使用提供的agent执行单步
- ✅ 不提供agent时自动创建

#### TestRunTestcasesForGui
- ✅ GUI模式测试用例执行

### 集成测试 (`test_cli_integration.py`)

#### TestCLIIntegration
- ✅ 完整的YAML处理流程
- ✅ 动作执行集成
- ✅ 错误处理集成
- ✅ 向后兼容性
- ✅ 混合动作类型

## 测试特性

### 模拟对象 (Mock Objects)
测试使用Python的`unittest.mock`模块来模拟外部依赖：
- ADBTool - 模拟Android调试桥接器
- AndroidAgent - 模拟Android代理
- 文件I/O操作
- 网络操作

### 临时文件处理
集成测试使用临时目录和文件来测试文件操作，确保测试隔离且不影响实际文件系统。

### 错误场景测试
全面测试各种错误场景：
- 文件不存在
- 格式错误的配置文件
- 网络异常
- 设备连接问题

### 向后兼容性测试
确保新功能不破坏现有的API和配置格式。

## 测试覆盖率

当前CLI模块的测试覆盖率约为**68%**，涵盖了所有主要功能路径和错误处理场景。

未覆盖的代码主要包括：
- `main()`函数的部分命令行参数处理
- 一些深层的错误处理路径
- 部分GUI特定的回调逻辑

## 测试最佳实践

1. **每个测试方法只测试一个功能点**
2. **使用描述性的测试方法名**
3. **适当使用setUp和tearDown方法**
4. **模拟外部依赖以确保测试隔离**
5. **测试正常流程和异常流程**
6. **使用断言验证预期结果**

## 添加新测试

在添加新功能时，请确保：

1. 为新功能添加相应的单元测试
2. 如果涉及多个模块交互，添加集成测试
3. 测试正常和异常情况
4. 更新测试文档

### 示例：添加新的动作类型测试

```python
def test_new_action_type(self):
    """测试新动作类型"""
    action_dict = {
        "type": "new_action",
        "parameter": "value",
        "taskName": "test_new_action"
    }
    
    result = execute_unified_action(
        action_dict,
        self.mock_agent,
        is_cli_mode=True
    )
    
    self.assertEqual(result.action, "finished")
    # 添加更多断言...
```