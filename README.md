# 现代投资年报数据系统（Streamlit 版）

现代投资股份有限公司 2022-2025 年年报表格数据浏览系统，支持年度切换、单位换算（元/万元/亿元）、章节目录导航、表格搜索、跨年对比与 CSV 导出。

- 数据源：`modern_investment.db`（SQLite，只读，2022-2025 年报表格逐单元格存储）
- 应用入口：`app.py`
- 部署平台：Streamlit Community Cloud

## 本地运行

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 部署到 Streamlit Community Cloud

1. 将本仓库推送至 GitHub（公开仓库）。
2. 访问 <https://share.streamlit.io/>，用 GitHub 账号登录。
3. 点击 "New app" → 选择本仓库、分支 `main`、主文件 `app.py` → Deploy。
4. 部署完成后即可通过 `https://<app-name>.streamlit.app` 公网访问。
