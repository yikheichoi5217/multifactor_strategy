# 多因子选股量化策略 | A-Share Multi-Factor Stock Selection Strategy

本项目实现了一个面向 A 股沪深300股票池的多因子选股与回测框架。策略基于成长、动量、质量三类因子构建综合评分，在月度调仓频率下选取得分最高的股票并进行等权配置。项目覆盖数据获取、因子构建、因子预处理、选股、回测、绩效评估与可视化分析，适合作为量化研究、因子测试和策略原型开发的示例项目。

## 1. 项目亮点

- 构建了完整的多因子选股流程：数据准备、因子计算、因子预处理、组合构建、回测评估。
- 使用成长、动量、质量三类经典因子，分别刻画企业成长性、价格趋势和盈利质量。
- 对因子进行 MAD 去极值、Z-Score 标准化，并预留市值/行业中性化接口。
- 实现逐日回测引擎，支持月度调仓、等权配置、交易成本、停牌估值和交易日志记录。
- 输出净值曲线、回撤曲线、月度收益热力图、因子 IC 与分组回测图。

---

## 2. 策略原理

### 2.1 股票池与回测区间

- 股票池：沪深300成分股
- 回测区间：2021-01-01 至 2022-12-31
- 调仓频率：月度调仓，每月最后一个交易日调仓
- 持仓数量：Top 30
- 权重方式：等权配置
- 初始资金：10,000,000
- 单边交易成本：0.15%
- 基准指数：沪深300

### 2.2 多因子选股逻辑

策略核心思想是：不同因子从不同维度刻画公司/资产特征，单一因子可能失效或阶段性表现不稳定，而多因子组合可以降低单因子噪声，提升组合稳定性。  
本项目流程为：  
1. 计算三类因子；  
2. 对因子进行去极值、标准化、中性化；  
3. 按权重合成综合得分；  
4. 每月最后一个交易日选取得分最高的 10 只股票；  
5. 等权配置并进行回测。

### 2.3 三个因子的金融含义

本项目构建三类因子，并对不同维度的信息进行加权合成。

| 因子类别 | 使用指标 | 经济含义 |
|---|---|---|
| Growth 成长因子 | 营业收入同比增速、净利润同比增速 | 衡量公司业务扩张与盈利增长能力 |
| Momentum 动量因子 | 过去 20 日、60 日收益率，排除最近 5 日 | 捕捉中期价格趋势，同时降低短期反转噪声 |
| Quality 质量因子 | ROE、毛利率 | 衡量资本回报效率与盈利质量 |

综合得分采用加权求和方式：

```python
score = 0.33 * growth + 0.34 * momentum + 0.33 * quality
```

### 2.4 因子预处理

原始因子常存在极端值、量纲不一致、风格暴露（如市值偏好）等问题，因此本项目采用：

- **去极值（MAD）**：降低异常值对截面分布的影响；
- **标准化（Z-Score）**：统一量纲，使因子可比较与可加权；
- **中性化（OLS 残差）**：剔除市值/行业等非目标暴露，提高因子“纯度”。

---

## 3. 项目结构

```text
quant/
├── data/
│   ├── stock_pool.csv
│   ├── price_data.csv
│   ├── financial_data.csv
│   └── benchmark.csv
├── src/
│   ├── __init__.py
│   ├── data_loader.py
│   ├── factors/
│   │   ├── __init__.py
│   │   ├── growth_factor.py
│   │   ├── momentum_factor.py
│   │   └── quality_factor.py
│   ├── factor_processor.py
│   ├── stock_selector.py
│   ├── backtest_engine.py
│   └── performance.py
├── results/
│   ├── factor_analysis/
│   ├── backtest/
│   └── metrics.txt
├── generate_data_py311.py
├── config.py
├── main.py
└── README.md
```

各模块作用说明：

- `config.py`：统一配置回测参数、因子权重、路径；
- `src/data_loader.py`：负责下载并加载股票池、行情、财务、基准数据；
- `src/factors/*.py`：三类因子计算；
- `src/factor_processor.py`：因子去极值、标准化、中性化；
- `src/stock_selector.py`：多因子加权综合评分与 TopN 选股；
- `src/backtest_engine.py`：逐日回测、调仓、交易成本处理、日志记录；
- `src/performance.py`：绩效指标计算与图形化分析；
- `main.py`：主流程编排与结果输出。

---

## 4. 环境配置步骤

> 约束：Python 3.6，依赖版本需与项目一致。

### 4.1 使用 conda 创建环境

```bash
conda create -n quant python=3.6 -c conda-forge
conda activate quant
```

### 4.2 安装依赖

```bash
cd multifactor_strategy
pip install -r requirements.txt
```


---

## 5. 运行步骤

### 5.1 首次运行

由于 AKShare 和部分数据接口对 Python 版本兼容性有要求，数据生成脚本建议在 Python 3.11 环境下运行：

```bash
cd multifactor_strategy
conda create --name data python=3.11
conda activate data
pip install -r generate_data_requirements.txt
```
```bash
python generate_data_py311.py
```

该脚本会生成以下本地 CSV 文件：
data/
├── stock_pool.csv
├── price_data.csv
├── financial_data.csv
└── benchmark.csv




### 5.2 运行主流程

```bash
python main.py
```

---

## 6. 输出说明

程序运行后，主要输出位于 `results/`：

1. `results/metrics.txt`  
   主要绩效指标文本，包括：
   - 累计收益率、年化收益率、年化波动率
   - 夏普比率、最大回撤、Calmar 比率
   - 超额累计收益、超额年化收益、信息比率、超额最大回撤
   - 月度胜率（相对基准）

2. `results/backtest/net_value_vs_benchmark.png`  
   策略净值 vs 沪深300基准净值曲线，用于观察绝对与相对表现。

3. `results/backtest/drawdown.png`  
   回撤曲线，用于评估风险暴露和资金回撤深度。

4. `results/backtest/monthly_returns_heatmap.png`  
   月度收益热力图（行=年份，列=月份），直观看收益分布与稳定性。

5. `results/factor_analysis/*_ic.png`  
   各因子的 IC 时序图，用于验证截面预测能力与稳定性。

6. `results/factor_analysis/*_grouping.png`  
   各因子的分组回测图，观察高分组与低分组是否存在显著收益分层。

---

## 7.回测结果
## 回测结果

回测区间为 2021-01-01 至 2022-12-31，基准指数为沪深300。

| 指标 | 策略表现 | 沪深300基准 |
|---|---:|---:|
| 累计收益率 | -4.05% | -32.32% |
| 年化收益率 | -2.13% | -15.97% |
| 年化波动率 | 24.09% | - |
| 夏普比率 | -0.21 | - |
| 最大回撤 | -38.02% | - |
| 超额累计收益 | 28.27% | - |
| 超额年化收益 | 13.84% | - |
| 信息比率 | 0.76 | - |
| 月度胜率 | 56.52% | - |

从回测结果看，策略在 2021-2022 年的绝对收益率为 -4.05%，仍有进一步优化空间；但同期沪深300累计收益率约为 -32.32%，策略相对基准取得了 28.27% 的超额累计收益，年化超额收益为 13.84%。这说明在市场整体下行的样本区间内，多因子选股组合具备一定的相对抗跌能力和超额收益表现。


## 8. 免责声明

本项目仅用于量化研究、教学与技术交流，不构成任何投资建议或收益承诺。  
策略回测结果基于历史数据，无法保证未来表现；实盘交易需考虑滑点、冲击成本、交易规则变化、数据质量等实际因素。  
使用者应独立评估相关风险并自行承担投资决策后果。

