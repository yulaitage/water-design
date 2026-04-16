# {{ project_name }}工程量统计与费用估算表

## 基本信息

| 项目 | 内容 |
|------|------|
| 项目名称 | {{ project_name }} |
| 项目类型 | {{ project_type }} |
| 估算日期 | {{ estimate_date }} |
| 估算版本 | v{{ version }} |

## 设计参数

| 参数名称 | 数值 | 单位 |
|----------|------|------|
{% for key, value in design_params.items() %}
| {{ key }} | {{ value }} | - |
{% endfor %}

## 工程量汇总

| 工程项目类别 | 总工程量 | 单位 | 总费用(元) |
|--------------|----------|------|------------|
{% for item in summary %}
| {{ item.category }} | {{ "%.2f"|format(item.total_quantity) }} | {{ item.unit }} | {{ "%.2f"|format(item.total_amount) }} |
{% endfor %}

| **合计** | - | - | **{{ "%.2f"|format(total_cost) }}** |
{% if cost_per_km %}
| 单位造价 | {{ "%.2f"|format(cost_per_km) }} | 万元/km | - |
{% endif %}

## 分项工程量明细

### {% for category in details | groupby('category') %}
#### {{ category }}
| 序号 | 工程名称 | 工程量 | 单位 | 单价(元) | 小计(元) |
|------|----------|--------|------|----------|----------|
{% for item in category.items %}
| {{ loop.index }} | {{ item.item }} | {{ "%.2f"|format(item.quantity) }} | {{ item.unit }} | {{ "%.2f"|format(item.unit_price) }} | {{ "%.2f"|format(item.subtotal) }} |
{% endfor %}
{% endfor %}

---
编制单位: {{ org_name }}
审核: {{ reviewer }}
编制: {{ preparer }}