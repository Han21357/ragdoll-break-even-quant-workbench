# 量化选股策略定制器 · 设计文档

## 一、GitHub 类似项目调研

| 项目 | 地址 | 核心特点 | 可借鉴 |
|------|------|----------|--------|
| a-share-quant-selector | github.com/Dzy-HW-XD/a-share-quant-selector | A股量化选股系统，碗口反弹策略，Web界面+钉钉通知 | Web管理界面、K线图可视化、智能分类 |
| stock-analysis | github.com/balabala-sean/stock-analysis | A股量化脚手架，均值回归策略，多因子组合扩展 | 因子开发框架、配置驱动策略、邮件信号触达 |
| quant_project | github.com/zhangjc138/quant_project | MA20角度选股+RSI/MACD+机器学习预测 | 5维度评分系统、回测统计指标（夏普/索提诺/最大回撤） |
| PKScreener | github.com/pkjmesra/PKScreener | 开源股票筛选工具，可编程规则引擎 | 规则引擎设计、批量扫描、多市场支持 |
| stock-strategies-only | github.com/skyline891/stock-strategies-only | 台股选股机器人，多流派因子×大盘regime自适应 | 大盘regime自适应策略切换、多AI专家协作设计 |

### 调研结论
- **因子库设计**：主流项目都用分类因子库（趋势/动量/基本面/过滤），我们的威科夫因子是差异化优势
- **策略编辑**：PKScreener 的规则引擎最接近我们想要的「拖拽组合条件」体验
- **回测指标**：quant_project 的5维度评分（趋势/动量/波动率/RSI/MACD）+ 夏普/最大回撤/胜率值得参考
- **regime自适应**：stock-strategies-only 的「大盘regime→自动切换策略参数」是高级特性，可作为V2目标

---

## 二、数据接口规格（预留）

### 2.1 因子库接口

```
GET /api/quant/factors
```
返回所有可用因子，按分类组织。

**响应示例：**
```json
{
  "categories": [
    {
      "name": "trend",
      "label": "趋势类",
      "factors": [
        {"id": "ma20_angle", "name": "MA20角度", "type": "number", "params": [{"key": "threshold", "label": "角度阈值", "default": 30, "min": 0, "max": 90}]},
        {"id": "macd_cross", "name": "MACD金叉", "type": "bool", "params": []},
        {"id": "ma_bullish", "name": "均线多头排列", "type": "bool", "params": [{"key": "periods", "label": "均线周期", "default": "5,10,20,60"}]}
      ]
    },
    {
      "name": "momentum",
      "label": "动量类",
      "factors": [
        {"id": "rsi_range", "name": "RSI区间", "type": "range", "params": [{"key": "min", "default": 30}, {"key": "max", "default": 50}]},
        {"id": "rsi_strong", "name": "RSI强势区间", "type": "bool", "params": [{"key": "threshold", "default": 60}]},
        {"id": "volume_breakout", "name": "成交量突破", "type": "bool", "params": [{"key": "multiplier", "label": "均量倍数", "default": 2.0}]}
      ]
    },
    {
      "name": "wyckoff",
      "label": "威科夫",
      "factors": [
        {"id": "spring_signal", "name": "Spring信号", "type": "bool", "params": []},
        {"id": "sos_breakout", "name": "SOS突破", "type": "bool", "params": []},
        {"id": "accumulation", "name": "Accumulation阶段", "type": "bool", "params": []},
        {"id": "markup", "name": "Markup启动", "type": "bool", "params": []}
      ]
    },
    {
      "name": "fundamental",
      "label": "基本面",
      "factors": [
        {"id": "pe_percentile", "name": "PE分位", "type": "range", "params": [{"key": "max", "default": 30}]},
        {"id": "roe_filter", "name": "ROE过滤", "type": "number", "params": [{"key": "min", "default": 15}]},
        {"id": "market_cap", "name": "市值过滤", "type": "number", "params": [{"key": "min_yi", "default": 50}]}
      ]
    },
    {
      "name": "filter",
      "label": "过滤类",
      "factors": [
        {"id": "exclude_st", "name": "排除ST/退市", "type": "bool", "params": []},
        {"id": "north_flow", "name": "北向资金流入", "type": "bool", "params": [{"key": "days", "default": 3}]}
      ]
    }
  ]
}
```

### 2.2 策略保存接口

```
POST /api/quant/strategy
PUT  /api/quant/strategy/:id
GET  /api/quant/strategy
GET  /api/quant/strategy/:id
DELETE /api/quant/strategy/:id
```

**策略 JSON 结构：**
```json
{
  "id": "spring_momentum_v1",
  "name": "春季攻势_威科夫+动量",
  "public": true,
  "created_at": "2026-07-13T23:00:00",
  "steps": [
    {
      "step": 1,
      "label": "市场过滤",
      "logic": "AND",
      "conditions": [
        {"factor": "exclude_st", "params": {}},
        {"factor": "market_cap", "params": {"min_yi": 50}}
      ]
    },
    {
      "step": 2,
      "label": "威科夫阶段筛选",
      "logic": "OR",
      "conditions": [
        {"factor": "spring_signal", "params": {}, "required": true},
        {"factor": "accumulation", "params": {}}
      ]
    },
    {
      "step": 3,
      "label": "动量确认",
      "logic": "AND",
      "conditions": [
        {"factor": "rsi_range", "params": {"min": 30, "max": 50}},
        {"factor": "volume_breakout", "params": {"multiplier": 2.0}}
      ]
    },
    {
      "step": 4,
      "label": "排序与上限",
      "sort_by": "ma20_angle",
      "sort_order": "desc",
      "limit": 10
    }
  ]
}
```

### 2.3 策略执行接口（异步）

```
POST /api/quant/run          → 返回 task_id
GET  /api/quant/run/:task_id  → 轮询结果
```

**执行请求：**
```json
{
  "strategy_id": "spring_momentum_v1",
  "board": "all",
  "date": "latest"
}
```

**执行结果：**
```json
{
  "status": "done",
  "matched_count": 10,
  "results": [
    {
      "code": "603019",
      "name": "中科曙光",
      "matched_factors": ["spring_signal", "rsi_range", "volume_breakout"],
      "ma20_angle": 42.3,
      "rsi": 38.5,
      "volume_ratio": 2.8,
      "phase": "Markup",
      "price": 87.30,
      "change_pct": 3.2
    }
  ]
}
```

### 2.4 策略回测接口（异步）

```
POST /api/quant/backtest     → 返回 task_id
GET  /api/quant/backtest/:task_id
```

**回测请求：**
```json
{
  "strategy_id": "spring_momentum_v1",
  "months": 12,
  "hold_days": 10,
  "top_n": 10
}
```

**回测结果：**
```json
{
  "status": "done",
  "stats": {
    "annual_return": 28.3,
    "max_drawdown": -12.4,
    "sharpe_ratio": 1.82,
    "win_rate": 64,
    "total_trades": 120,
    "avg_hold_days": 9.5,
    "profit_factor": 2.1
  },
  "monthly_returns": [
    {"month": "2025-07", "return": 5.2},
    {"month": "2025-08", "return": -3.1}
  ],
  "benchmark": {
    "name": "沪深300",
    "annual_return": 8.5,
    "max_drawdown": -15.2,
    "sharpe_ratio": 0.62
  }
}
```

---

## 三、前端实现要点

### 3.1 页面结构
- 左栏：因子库（可拖拽，按分类折叠）
- 中栏：条件组合区（4步编辑器，每步可加 AND/OR 条件）
- 右栏/底部：回测预览（收益曲线 + 统计指标）

### 3.2 交互流程
1. 从因子库拖拽因子到条件组合区
2. 每加一个条件，实时调用 `/api/quant/preview` 估算命中数量
3. 点击「运行回测」→ POST `/api/quant/backtest` → 轮询结果
4. 点击「保存策略」→ POST `/api/quant/strategy`
5. 点击「导出JSON」→ 下载策略 JSON 文件

### 3.3 与现有系统集成
- 新增侧边栏菜单项：「量化选股」→ 切换到 panel-quant
- 策略保存后可在「全市场漏斗」中选择已保存策略执行
- 回测结果可对比现有 `wyckoff backtest` 的结果

---

## 四、CLI 功能审计总结

### 已验证可用（8/22）
| 命令 | 功能 | Web 对接状态 |
|------|------|-------------|
| screen | 全市场漏斗筛选 | ✅ /api/screen |
| backtest | 策略历史回测 | ✅ /api/backtest |
| report | AI深度研报 | ✅ /api/report |
| signal | 信号确认池 | ✅ /api/signals |
| recommend | 形态复盘 | ⚠️ 待对接 |
| config | 数据源配置 | ✅ /api/model/list |
| model | 模型管理 | ✅ /api/model/list |
| portfolio | 持仓管理(本地) | ✅ /api/portfolio |

### 需要登录（5/22）
auth / sync / memory / workflow / session — 需要 Supabase 账号

### 辅助功能（9/22）
dashboard / mcp / log / trace / prompt / diag / cleanup / update / workflow — 可用但非核心

### 待开发接口（3个）
- `/api/quant/factors` — 因子库
- `/api/quant/strategy` — 策略 CRUD
- `/api/quant/run` — 策略执行
- `/api/quant/backtest` — 策略回测
