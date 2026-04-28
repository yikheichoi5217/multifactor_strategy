# 多因子选股量化策略（AKShare + Python 3.6）

## 1. 项目简介

本项目实现了一个可直接运行的 A 股多因子选股策略框架，围绕“成长、动量、质量”三类经典因子构建综合评分，并在月度调仓频率下进行组合回测。项目包含数据下载、因子计算、因子预处理、选股、回测引擎、绩效分析与可视化全流程，适合作为量化策略研究与教学模板。

---

## 2. 策略原理

### 2.1 多因子选股逻辑

策略核心思想是：不同因子从不同维度刻画公司/资产特征，单一因子可能失效或阶段性表现不稳定，而多因子组合可以降低单因子噪声，提升组合稳定性。  
本项目流程为：  
1. 计算三类因子；  
2. 对因子进行去极值、标准化、中性化；  
3. 按权重合成综合得分；  
4. 每月最后一个交易日选取得分最高的 10 只股票；  
5. 等权配置并进行回测。

### 2.2 三个因子的金融含义

1. **成长因子（Growth）**  
   使用营业收入同比增速与净利润同比增速，反映企业经营扩张与盈利成长能力。

2. **动量因子（Momentum）**  
   使用过去 20 日与 60 日收益率（排除最近 5 日），捕捉中期趋势并规避短期反转干扰。

3. **质量因子（Quality）**  
   使用 ROE 与毛利率，反映公司资本回报能力与盈利质量。

### 2.3 为什么要做因子预处理

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
├── config.py
├── main.py
├── requirements.txt
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

> 约束：Python 3.6，Windows，依赖版本需与项目一致。

### 4.1 使用 conda 创建环境

```bash
conda create -n quant python=3.6 -c conda-forge
conda activate quant
```

### 4.2 安装依赖

```bash
conda install pandas numpy scipy statsmodels matplotlib seaborn
```


---

## 5. 运行步骤

### 5.1 首次运行

首次运行前需使用generate_data_py311.py准备数据（需在Python3.11环境下运行，后续步骤均在Python3.6运行）

运行命令：

```bash
python main.py
```

### 5.2 后续运行

后续默认直接读取本地 CSV，避免重复拉取数据，提升运行效率。

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

## 7. 免责声明

本项目仅用于量化研究、教学与技术交流，不构成任何投资建议或收益承诺。  
策略回测结果基于历史数据，无法保证未来表现；实盘交易需考虑滑点、冲击成本、交易规则变化、数据质量等实际因素。  
使用者应独立评估相关风险并自行承担投资决策后果。

