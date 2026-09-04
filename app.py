"""现代投资年报数据系统 - Streamlit 版
数据源：modern_investment.db（2022-2025 年报表格，SQLite 只读）
部署：Streamlit Community Cloud + GitHub 公开仓库
"""

import csv
import io
import re
import sqlite3
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from pathlib import Path

import streamlit as st

DB_PATH = Path(__file__).parent / "modern_investment.db"

# ==================== 章节/前缀词表（与 Flask 版一致） ====================
PREFIXES = [
    '母公司财务报表主要项目注释', '合并财务报表项目注释', '递延所得税资产/递延所得税负债',
    '递延所得税资产-递延所得税负债', '重要会计政策和会计估计变更', '与上年度财务报告相比',
    '在子公司的所有者权益份额发生变化且仍控制子公司的交易', '在合营企业或联营企业中的权益',
    '在子公司中的权益', '在其他主体中的权益', '内部控制评价报告或内部控制审计报告',
    '重要会计政策及会计估计', '董事会下设专门委员会在报告期内的情况',
    '董事和高级管理人员情况', '报告期内董事履行职责的情况', '股东和实际控制人情况',
    '资产及负债状况分析', '截至报告期末公司近两年的主要会计数据和财务指标',
    '涉及政府补助的负债项目', '计入当期损益的政府补助', '与金融工具相关的风险',
    '公司开展符合条件套期业务并应用套期会计', '公司开展套期业务进行风险管理',
    '本期发生的非同一控制下企业合并', '非同一控制下企业合并', '同一控制下企业合并',
    '公司利润分配及资本公积金转增股本情况', '公司报告期内对子公司的管理控制情况',
    '重大合同及其履行情况', '聘任、解聘会计师事务所情况', '重大诉讼、仲裁事项',
    '重要提示、目录和释义', '现金流量表补充资料', '现金流量表项目', '重大关联交易',
    '其他重大关联交易', '非金融企业债务融资工具', '外币财务报表的折算', '合并范围的变更',
    '主营业务分析', '收入与成本', '投资状况分析', '金融资产投资', '衍生品投资情况',
    '公司员工情况', '公司债券', '环境信息披露情况', '股份变动情况', '限售股份变动情况',
    '公允价值的披露', '关联方及关联交易', '关联交易情况', '关联方应收应付款项',
    '审计报告', '税项', '租赁', '研发支出', '分部信息', '补充资料',
    '财务报表',
]

REPLACEMENTS = [
    ('按坏账计提方法分类披露', '坏账分类'),
    ('本期计提、收回或转回的坏账准备情况', '坏账准备变动'),
    ('本期计提、收回或转回的坏账准备的情况', '坏账准备变动'),
    ('按欠款方归集的期末余额前五名的应收账款和合同资产情况', '应收账款前五大欠款方'),
    ('按欠款方归集的期末余额前五名的其他应收款情况', '其他应收款前五大欠款方'),
    ('截至报告期末的资产权利受限情况', '资产权利受限情况'),
    ('报告期内获取的重大的股权投资情况', '重大股权投资情况'),
    ('报告期内以套期保值为目的的衍生品投资', '套期保值衍生品投资'),
    ('报告期内接待调研、沟通、采访等活动', '接待调研与采访活动'),
    ('董事会下设专门委员会在报告期内的情况', '专门委员会情况'),
    ('公司利润分配及资本公积金转增股本情况', '利润分配及转增股本情况'),
    ('公司报告期内对子公司的管理控制情况', '对子公司的管理控制情况'),
    ('会计政策、会计估计变更或重大会计差错更正的情况说明', '会计政策估计变更及差错更正'),
    ('合并报表范围发生变化的情况说明', '合并范围变化情况'),
    ('与存在关联关系的财务公司的往来情况', '与财务公司的关联往来'),
    ('其他持股在10%以上的法人股东', '持股10%以上的法人股东'),
    ('非金融企业债务融资工具基本信息', '债务融资工具基本信息'),
    ('截至报告期末公司近两年的主要会计数据和财务指标', '主要会计数据与财务指标'),
    ('2025年起首次执行新会计准则调整首次执行当年年初财务报表相关项目情况', '首次执行新准则调整情况'),
    ('2025年起首次执行新会计准则调整', '首次执行新会计准则调整'),
    ('存货跌价准备和合同履约成本减值准备', '存货跌价及合同履约成本减值'),
    ('期末重要的一年内到期的债权投资', '一年内到期的重要债权投资'),
    ('一年内到期的债权投资-减值准备计提情况', '到期债权投资减值准备'),
    ('一年内到期的非流动资产-一年内到期的长期应收款', '一年内到期长期应收款'),
    ('其他债权投资-减值准备计提情况', '其他债权投资减值准备'),
    ('采用成本计量模式的投资性房地产', '成本模式投资性房地产'),
    ('未办妥产权证书的投资性房地产情况', '未办证投资性房地产'),
    ('商誉所在资产组或资产组组合的相关信息', '商誉所在资产组信息'),
    ('商誉-可收回金额的具体确定方法', '商誉可收回金额确定方法'),
    ('以抵销后净额列示的递延所得税资产/负债', '以抵销净额列示的递延所得税'),
    ('以抵销后净额列示的递延所得税资产-负债', '以抵销净额列示的递延所得税'),
    ('以抵销后净额列示的递延所得税资产和递延所得税负债', '以抵销净额列示的递延所得税'),
    ('以抵销后净额列示的递延所得税资产或负债', '以抵销净额列示的递延所得税'),
    ('递延所得税资产/递延所得税负债-未确认递延所得税资产的可抵扣亏损将于以下年度到期', '未确认递延所得税到期'),
    ('未确认递延所得税资产的可抵扣亏损', '未确认递延所得税资产'),
    ('账龄超过1年或逾期的重要应付账款', '账龄超1年重要应付账款'),
    ('账龄超过1年或逾期的重要其他应付款', '账龄超1年重要其他应付款'),
    ('设定提存计划列示', '设定提存计划'),
    ('（不包括划分为金融负债的优先股、永续债等其他金融工具）', ''),
    ('合同资产-报告期内账面价值发生的重大变动金额和原因', '合同资产-账面价值重大变动'),
    ('报告期内账面价值发生的重大变动金额和原因', '账面价值重大变动'),
    ('划分为金融负债的其他金融工具说明', '金融负债工具说明'),
    ('其他权益工具-期末发行在外的优先股、永续债等金融工具变动情况表', '优先股永续债变动情况'),
    ('期末发行在外的优先股、永续债等金融工具变动情况表', '优先股永续债变动情况'),
    ('占公司营业收入或营业利润10%以上的行业、产品、地区、销售模式的情况', '占收入或利润10%以上明细'),
    ('本期支付的取得子公司的现金净额', '取得子公司支付的现金净额'),
    ('本期收到的处置子公司的现金净额', '处置子公司收到的现金净额'),
    ('不属于现金及现金等价物的货币资金', '非现金等价物的货币资金'),
    ('本期发生的非同一控制下企业合并', '本期非同一控制下企业合并'),
    ('被购买方于购买日可辨认资产、负债', '被购买方可辨认资产负债'),
    ('合并日被合并方资产、负债的账面价值', '合并日被合并方账面价值'),
    ('重要非全资子公司的主要财务信息', '重要非全资子公司财务信息'),
    ('交易对于少数股东权益及归属于母公司所有者权益的影响', '对少数股东及母公司权益的影响'),
    ('不重要的合营企业和联营企业的汇总财务信息', '不重要的合营及联营企业汇总'),
    ('在未纳入合并财务报表范围的结构化主体中的权益', '结构化主体中的权益'),
    ('公司开展符合条件套期业务并应用套期会计', '符合条件的套期业务与套期会计'),
    ('以公允价值计量的资产和负债的期末公允价值', '公允价值计量的资产负债'),
    ('购销商品、提供和接受劳务的关联交易', '购销商品与劳务关联交易'),
    ('对联营、合营企业投资', '联营合营投资'),
]

CHAPTERS = [
    ('第一节 重要提示、目录和释义', ['重要提示、目录和释义', '重要提示', '目录']),
    ('第二节 公司简介和主要财务指标', ['公司信息', '联系人和联系方式', '信息披露及备置地点',
        '注册变更情况', '其他有关资料', '主要会计数据和财务指标', '分季度主要财务指标', '非经常性损益项目']),
    ('第三节 管理层讨论与分析', ['主营业务分析', '收入与成本', '费用', '研发投入', '现金流',
        '资产及负债状况分析', '投资状况分析', '金融资产投资', '衍生品投资', '公司员工情况',
        '报告期内合并范围是否发生变动', '主要销售客户和主要供应商情况', '占公司营业收入或营业利润',
        '主要控股参股公司']),
    ('第四节 公司治理', ['公司治理', '股东和实际控制人情况', '董事和高级管理人员情况',
        '董事会下设专门委员会', '报告期内董事履行职责', '公司利润分配及资本公积金转增股本情况',
        '公司报告期内对子公司的管理控制情况']),
    ('第五节 环境和社会责任', ['环境信息披露', '环境信息', '社会责任']),
    ('第六节 重要事项', ['重大诉讼', '重大合同', '聘任、解聘会计师事务所', '重大关联交易',
        '其他重大关联交易', '与存在关联关系的财务公司', '报告期内接待调研、沟通、采访']),
    ('第七节 股份变动及股东情况', ['股份变动情况', '限售股份变动情况', '持股在10%以上', '其他持股']),
    ('第八节 优先股相关情况', ['优先股', '永续债', '其他权益工具']),
    ('第九节 债券相关情况', ['公司债券', '非金融企业债务融资工具', '应付债券']),
    ('第十节 财务报告', ['审计报告', '财务报表', '合并财务报表项目注释', '母公司财务报表主要项目注释',
        '重要会计政策和会计估计', '重要会计政策及会计估计', '与上年度财务报告相比', '首次执行新会计准则',
        '税项', '租赁', '研发支出', '分部信息', '补充资料', '现金流量表', '外币财务报表的折算', '外币',
        '合并范围的变更', '应收', '存货', '合同资产', '长期股权投资', '投资性房地产', '固定资产',
        '在建工程', '使用权资产', '无形资产', '商誉', '长期待摊费用', '递延所得税', '应付', '应交税费',
        '所得税', '公允价值', '与金融工具相关的风险', '政府补助', '套期', '非同一控制下企业合并',
        '同一控制下企业合并', '在子公司中的权益', '在子公司的所有者权益份额',
        '在合营企业或联营企业中的权益', '在其他主体中的权益', '关联', '按欠款方归集', '账龄超过',
        '以抵销后净额列示', '未确认递延所得税资产', '划分为金融负债', '一年内到期的', '少数股东权益',
        '预付款项', '债权投资', '借款', '预收款项']),
]

# ==================== 数据库（只读） ====================
def _conn():
    return sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)


@st.cache_data(ttl=3600)
def get_years():
    c = _conn()
    rows = c.execute("SELECT DISTINCT year FROM table_metadata ORDER BY year").fetchall()
    c.close()
    return [r[0] for r in rows]


def _short_name(name):
    n = name.strip()
    for old, new in REPLACEMENTS:
        if old in n:
            n = n.replace(old, new)
    for p in sorted(PREFIXES, key=len, reverse=True):
        for sep in ('-', '/', '—', '–', '，', ','):
            if n.startswith(p + sep):
                n = n[len(p) + len(sep):].strip()
                break
        else:
            continue
        break
    for suf in ('-合并', '-母公司'):
        if n.endswith(suf) and len(n) - len(suf) >= 4:
            n = n[:len(n) - len(suf)]
    if len(n) > 14:
        n = n[:12] + '…'
    return n


@st.cache_data(ttl=3600)
def _get_a2(year, sheet_name):
    c = _conn()
    row = c.execute(
        "SELECT cell_value FROM raw_tables WHERE year=? AND sheet_name=? AND row_num=2 AND col_num=1",
        (year, sheet_name)).fetchone()
    c.close()
    return row[0] if row and row[0] else None


def _sheet_display_name(year, sheet_name):
    a2 = _get_a2(year, sheet_name)
    if a2 and 6 <= len(a2) <= 80:
        return _short_name(a2)
    return _short_name(sheet_name)


def _match_chapter(name):
    best_ch, best_len = '未分类', 0
    for ch, kws in CHAPTERS:
        for kw in kws:
            if kw in name and len(kw) > best_len:
                best_ch, best_len = ch, len(kw)
    return best_ch


def _split_hierarchy(name):
    n = name.strip().replace('/', '-')
    for suf in ('-合并', '-母公司'):
        if n.endswith(suf):
            n = n[:-len(suf)]
            break
    parts = [p.strip() for p in n.split('-') if p.strip()]
    if len(parts) >= 3:
        return parts[0], parts[1], '-'.join(parts[2:])
    if len(parts) == 2:
        return parts[0], None, parts[1]
    return None, None, parts[0] if parts else n


@st.cache_data(ttl=3600)
def get_tree(year):
    c = _conn()
    rows = c.execute(
        "SELECT sheet_name FROM table_metadata WHERE year=? ORDER BY id", (year,)).fetchall()
    c.close()
    chapters = {ch: {} for ch, _ in CHAPTERS}
    chapters['未分类'] = {}
    for (sheet,) in rows:
        display = _sheet_display_name(year, sheet)
        a2 = _get_a2(year, sheet)
        name = a2 if (a2 and 6 <= len(a2) <= 80) else sheet
        ch = _match_chapter(name)
        sec, sub, _rest = _split_hierarchy(name)
        entry = {'sheet': sheet, 'display': display}
        node = chapters[ch]
        if sec is None:
            node.setdefault(display, []).append(entry)
        elif sub is None:
            node.setdefault(sec, []).append(entry)
        else:
            node.setdefault(sec + '/' + sub, []).append(entry)
    out = []
    for ch, _ in CHAPTERS:
        if chapters[ch]:
            out.append({'chapter': ch,
                        'sections': [{'name': k, 'tables': v} for k, v in chapters[ch].items()]})
    if chapters['未分类']:
        all_t = [t for s in chapters['未分类'].values() for t in s]
        out.append({'chapter': '未分类',
                    'sections': [{'name': '未分类表格', 'tables': all_t}]})
    return out


@st.cache_data(ttl=3600)
def get_grid(year, sheet):
    c = _conn()
    meta = c.execute(
        "SELECT pdf_page, row_count, col_count FROM table_metadata WHERE year=? AND sheet_name=?",
        (year, sheet)).fetchone()
    if not meta:
        c.close()
        return None
    cells = c.execute(
        "SELECT row_num, col_num, cell_value FROM raw_tables WHERE year=? AND sheet_name=?",
        (year, sheet)).fetchall()
    c.close()
    page, rn, cn = meta
    grid = [[None] * cn for _ in range(rn)]
    for (r, cc, v) in cells:
        if 1 <= r <= rn and 1 <= cc <= cn:
            grid[r - 1][cc - 1] = v
    return {'display': _sheet_display_name(year, sheet), 'page': page,
            'rows': rn, 'cols': cn, 'grid': grid}


@st.cache_data(ttl=3600)
def get_compare_list(sheet):
    c = _conn()
    years = [r[0] for r in c.execute(
        "SELECT DISTINCT year FROM table_metadata WHERE sheet_name=? ORDER BY year",
        (sheet,)).fetchall()]
    if len(years) < 2:
        t = c.execute(
            "SELECT cell_value FROM raw_tables WHERE sheet_name=? AND row_num=2 AND col_num=1 LIMIT 1",
            (sheet,)).fetchone()
        if t:
            m = c.execute(
                "SELECT DISTINCT year FROM table_metadata WHERE sheet_name IN "
                "(SELECT sheet_name FROM raw_tables WHERE row_num=2 AND col_num=1 AND cell_value=?) "
                "ORDER BY year", (t[0],)).fetchall()
            years = sorted({r[0] for r in m})
    out = []
    for y in years:
        target = sheet
        if not c.execute("SELECT 1 FROM table_metadata WHERE year=? AND sheet_name=?",
                         (y, sheet)).fetchone():
            t = c.execute(
                "SELECT cell_value FROM raw_tables WHERE sheet_name=? AND row_num=2 AND col_num=1 LIMIT 1",
                (sheet,)).fetchone()
            row = c.execute(
                "SELECT sheet_name FROM raw_tables WHERE year=? AND row_num=2 AND col_num=1 AND cell_value=? LIMIT 1",
                (y, t[0] if t else '')).fetchone()
            if not row:
                continue
            target = row[0]
        out.append((y, target))
    c.close()
    return out


@st.cache_data(ttl=3600)
def search_tables(year, q):
    c = _conn()
    rows = c.execute(
        "SELECT sheet_name FROM table_metadata WHERE year=? AND (sheet_name LIKE ? OR sheet_name IN "
        "(SELECT sheet_name FROM raw_tables WHERE year=? AND row_num=2 AND col_num=1 AND cell_value LIKE ?)) "
        "ORDER BY id", (year, f'%{q}%', year, f'%{q}%')).fetchall()
    c.close()
    return [{'sheet': r[0], 'display': _sheet_display_name(year, r[0])} for r in rows]


# ==================== 格式化（与 Flask 版 JS 逻辑一致） ====================
def clean_cell(v):
    if v is None:
        return v
    m = re.match(r"^HYPERLINK is not implemented[.] linkLocation=.*?, friendlyName=(.*)$", str(v))
    return m.group(1) if m else v


def parse_plain_num(s):
    if s is None:
        return None
    t = str(s).replace(',', '').replace(' ', '').strip()
    if t == '' or '%' in t:
        return None
    try:
        return float(t)
    except ValueError:
        return None


def is_num(s):
    if s is None or s == '':
        return False
    t = str(s).replace(',', '').replace('%', '').strip()
    if t == '':
        return False
    try:
        float(t)
        return True
    except ValueError:
        return False


def fmt_num(x, force_dec=False):
    try:
        f = float(x)
    except (TypeError, ValueError):
        return str(x)
    if f != f or f in (float('inf'), float('-inf')):
        return str(x)
    neg = f < 0
    a = abs(f)
    try:
        d = Decimal(str(a)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        # 超出常规财务数值范围的超大数（如目录链接的 numeric friendlyName）：原样显示
        s = str(a)
        if force_dec and '.' not in s:
            s += '.00'
        return ('-' if neg else '') + s
    if d == d.to_integral_value():
        s = str(int(d))
    else:
        s = f"{d:.2f}"
    if force_dec and '.' not in s:
        s += '.00'
    parts = s.split('.')
    parts[0] = f"{int(parts[0]):,}"
    return ('-' if neg else '') + '.'.join(parts)


def fmt_pct(s):
    num = s[:-1].replace(',', '').strip()
    try:
        n = float(num)
    except ValueError:
        return s
    return fmt_num(n, True) + '%'


def fmt_cell(v, is_pct, is_label, factor):
    cv = clean_cell(v)
    if cv is None:
        return None
    s = str(cv).strip()
    if s == '':
        return None
    if s.endswith('%'):
        return fmt_pct(s)
    n = parse_plain_num(s)
    if n is None:
        return s
    if is_pct:
        return fmt_num(n * 100, True) + '%'
    if factor != 1 and not is_label and abs(n) >= 10000:
        return fmt_num(n / factor, True)
    return fmt_num(n, False)


def analyze_grid(rows):
    n_cols = max((len(r) for r in rows), default=0)
    col_pct = [False] * n_cols
    kw_re = re.compile(r'%|增减|同比|占比|比重|比例|收益率')
    row_kw_re = re.compile(r'率|（%）|比例|占比')
    row_excl_re = re.compile(r'汇率|周转率|市盈率|元/股|每股收益')
    header_rows = min(len(rows), 25)
    kw_cols = {}
    for i in range(header_rows):
        r = rows[i] or []
        for j in range(1, len(r)):
            v = r[j]
            if v is None:
                continue
            t = str(clean_cell(v))
            if 'HYPERLINK' in t:
                continue
            if kw_re.search(t):
                kw_cols[j] = True
    col_nums = [[] for _ in range(n_cols)]
    for r in rows:
        for j in range(1, len(r)):
            n = parse_plain_num(clean_cell(r[j]))
            if n is not None:
                col_nums[j].append(n)

    def all_small(arr):
        return len(arr) > 0 and any(x != 0 for x in arr) and all(abs(x) <= 10 for x in arr)

    def frac_small(arr):
        return all_small(arr) and any(not float(x).is_integer() for x in arr)

    for j in kw_cols:
        if all_small(col_nums[j]):
            col_pct[j] = True
        elif j + 1 < n_cols and (j + 1) not in kw_cols and frac_small(col_nums[j + 1]):
            col_pct[j + 1] = True
    row_pct = []
    for r in rows:
        first = next((v for v in r if v is not None and str(v).strip() != ''), None)
        label = str(clean_cell(first)) if first is not None else ''
        row_pct.append(bool(row_kw_re.search(label)) and not bool(row_excl_re.search(label)))
    return col_pct, row_pct


NAV_RE = re.compile(r'^(首页|前一页|后一页|上一页|下一页|PDF 第.*页)$')


def _norm(s):
    return re.sub(r'\s+', ' ', str(s)).strip()


def is_nav_row(row):
    """导航垃圾行：首页/前一页/后一页/PDF 第X页（含 HYPERLINK 形式）。"""
    vals = [v for v in row if v is not None and str(v).strip() != '']
    if not vals:
        return False
    return all(NAV_RE.match(_norm(clean_cell(v))) for v in vals)


def clean_rows(rows):
    """去掉空行、导航垃圾行与含"年度报告"的页眉行。"""
    out = []
    for r in rows:
        vals = [v for v in r if v is not None and str(v).strip() != '']
        if not vals:
            continue
        if is_nav_row(r):
            continue
        if any('年度报告' in _norm(clean_cell(v)) for v in vals):
            continue
        out.append(r)
    return out


def is_title_row(row):
    filled = [v for v in row if v is not None and str(v).strip() != '']
    if not filled or len(filled) > 2:
        return False
    return not any(is_num(v) for v in filled)


def trim_grid(rows):
    if not rows:
        return rows
    n = max(len(r) for r in rows)
    keep = []
    for j in range(n):
        any_v = False
        for r in rows:
            v = r[j] if j < len(r) else None
            if v is not None and str(v).strip() != '':
                any_v = True
                break
        if any_v:
            keep.append(j)
    return [[r[j] for j in keep] for r in rows]


def render_grid(grid, factor):
    """返回格式化后的显示矩阵（字符串），标题行合并为单格（用于 CSV 导出）。"""
    rows = trim_grid(clean_rows(grid))
    col_pct, row_pct = analyze_grid(rows)
    out = []
    for r in rows:
        if is_title_row(r):
            text = '　'.join(str(v).strip() for v in r if v is not None and str(v).strip() != '')
            out.append([text] + [''] * (len(r) - 1))
            continue
        filled_idx = next((j for j, v in enumerate(r) if v is not None and str(v).strip() != ''), None)
        out.append([fmt_cell(v, col_pct[j], j == filled_idx, factor) or '' for j, v in enumerate(r)])
    return out


def _is_num_str(s):
    return bool(s) and bool(re.match(r'^-?\d[\d,]*(?:\.\d+)?%?$', str(s)))


_XDTZ_CSS = """
<style>
.xdtz-wrap { overflow-x: auto; }
table.xdtz { border-collapse: collapse; width: 100%;
  font-family: 'Microsoft YaHei','PingFang SC','Segoe UI',sans-serif;
  font-size: 13.5px; color: #23415c; background: #fff; }
table.xdtz td, table.xdtz th { border: 1px solid #d7e6f1; padding: 6px 12px;
  white-space: nowrap; text-align: left; }
table.xdtz tr:nth-child(even) td { background: #f6fafd; }
table.xdtz tr:hover td { background: #e8f4fb; }
table.xdtz tr.xdtz-band td { background: linear-gradient(90deg,#0a5c8c,#1377b5);
  color: #fff; font-weight: 700; text-align: center; font-size: 14px;
  letter-spacing: 1px; border: none; border-bottom: 2px solid #0a5c8c;
  padding: 9px 12px; }
table.xdtz th.xdtz-head { background: #dcecf7; color: #0a3d5e;
  font-weight: 700; text-align: center; }
table.xdtz td.xdtz-item { background: #f2f8fc; color: #1a4668; font-weight: 700; }
table.xdtz tr:nth-child(even) td.xdtz-item { background: #eaf3fa; }
table.xdtz td.xdtz-num { text-align: right; font-variant-numeric: tabular-nums; }
.xdtz-empty { color: #7a93a8; padding: 24px; text-align: center; font-size: 13px; }
</style>
"""


def esc_html(s):
    return (str(s).replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;'))


def render_table_html(grid, factor):
    """久其式表格：蓝色标题带合并行、浅蓝表头、斑马纹、数字右对齐。"""
    rows = clean_rows(grid)
    if not rows:
        return "<div class='xdtz-empty'>无数据</div>"
    rows = trim_grid(rows)
    if not rows:
        return "<div class='xdtz-empty'>无数据</div>"
    col_pct, _row_pct = analyze_grid(rows)
    n = max(len(r) for r in rows)
    seen_num = False
    parts = [_XDTZ_CSS, "<div class='xdtz-wrap'><table class='xdtz'>"]
    for r in rows:
        vals = [v for v in r if v is not None and str(v).strip() != '']
        if is_title_row(r):
            text = '　'.join(str(v).strip() for v in vals)
            parts.append(f"<tr class='xdtz-band'><td colspan='{n}'>{esc_html(text)}</td></tr>")
            continue
        filled_idx = next((j for j, v in enumerate(r) if v is not None and str(v).strip() != ''), 0)
        # 表头行：数据出现前、≥2 格、全部非数字
        if not seen_num and len(vals) >= 2 and not any(is_num(v) for v in vals):
            cells = []
            for j in range(n):
                raw = r[j] if j < len(r) else None
                v = fmt_cell(raw, col_pct[j], j == filled_idx, factor) if raw is not None else ''
                cells.append(f"<th class='xdtz-head'>{esc_html(v or '')}</th>")
            parts.append("<tr>" + "".join(cells) + "</tr>")
            continue
        if any(is_num(v) for v in vals):
            seen_num = True
        cells = []
        for j in range(n):
            raw = r[j] if j < len(r) else None
            v = fmt_cell(raw, col_pct[j], j == filled_idx, factor) if raw is not None else ''
            s = str(v or '')
            if j == filled_idx:
                cls = "xdtz-item"
            elif _is_num_str(s):
                cls = "xdtz-num"
            else:
                cls = "xdtz-txt"
            cells.append(f"<td class='{cls}'>{esc_html(s)}</td>")
        parts.append("<tr>" + "".join(cells) + "</tr>")
    parts.append("</table></div>")
    return "".join(parts)


def grid_to_csv(rows):
    buf = io.StringIO()
    w = csv.writer(buf)
    for r in clean_rows(rows):
        w.writerow([v if v is not None else '' for v in r])
    return buf.getvalue().encode('utf-8-sig')


# ==================== 页面 ====================
st.set_page_config(page_title="现代投资年报数据系统", layout="wide")

TAB_LIMIT = 40

years = get_years()
if 'cur_year' not in st.session_state:
    st.session_state.cur_year = None
if 'cur_sheet' not in st.session_state:
    st.session_state.cur_sheet = None
if 'cur_sec' not in st.session_state:
    st.session_state.cur_sec = None
if 'mode' not in st.session_state:
    st.session_state.mode = 'sec'

with st.sidebar:
    st.markdown("""
    <div style="background:linear-gradient(135deg,#0a5c8c,#1b7fb8); border-radius:8px;
                padding:10px 14px; margin-bottom:12px;">
      <div style="color:#fff; font-weight:700; font-size:15px;">现代投资年报数据系统</div>
      <div style="color:#cfe8f7; font-size:11px; margin-top:2px;">2022–2025 年报表格 · 久其式页签浏览</div>
    </div>""", unsafe_allow_html=True)

    year = st.selectbox("年度", years, index=len(years) - 1, key="year_sel")
    unit = st.selectbox("单位", ["元", "万元", "亿元"], key="unit_sel")
    factor = {"元": 1, "万元": 1e4, "亿元": 1e8}[unit]

    if st.session_state.cur_year != year:
        st.session_state.cur_year = year
        st.session_state.cur_sheet = None
        st.session_state.cur_sec = None
        st.session_state.mode = 'sec'

    tree = get_tree(year)

    # 搜索：直开单表（搜索优先于节视图；点节则切回节视图）
    q = st.text_input("搜索表格", key=f"q_{year}", placeholder="输入表名或标题关键词")
    if q.strip():
        matches = search_tables(year, q.strip())
        if matches:
            labels, mapping = [], {}
            for m in matches:
                label = m['display']
                if label in mapping:
                    label = f"{label}（{m['sheet']}）"
                mapping[label] = m['sheet']
                labels.append(label)
            prev_q = st.session_state.get(f"srch_q_{year}")
            if q != prev_q:
                st.session_state.pop(f"srch_{year}", None)
                st.session_state.pop(f"srch_prev_{year}", None)
                st.session_state.mode = 'srch'
                st.session_state.cur_sheet = matches[0]['sheet']
            st.session_state[f"srch_q_{year}"] = q
            prev = st.session_state.get(f"srch_prev_{year}")
            val = st.selectbox(
                f"搜索结果（{len(labels)}）", labels, key=f"srch_{year}",
                label_visibility="collapsed")
            if prev is not None and val != prev:
                st.session_state.cur_sheet = mapping[val]
                st.session_state.mode = 'srch'
            st.session_state[f"srch_prev_{year}"] = val
        else:
            st.caption("无匹配结果")

    # 默认：第一节（须在章 expander 渲染前确定，保证活动章自动展开）
    if st.session_state.cur_sec is None:
        for ci, ch in enumerate(tree):
            secs = [s for s in ch['sections'] if s['tables']]
            if secs:
                st.session_state.cur_sec = (ci, 0)
                break

    # 章节目录：点"节"后主区以横向页签展示该节全部表（久其式）
    st.markdown("**章　节　目　录**")
    for ci, ch in enumerate(tree):
        secs = [s for s in ch['sections'] if s['tables']]
        if not secs:
            continue
        active = st.session_state.cur_sec is not None and st.session_state.cur_sec[0] == ci
        with st.expander(ch['chapter'], expanded=active):
            options = [f"{s['name']}（{len(s['tables'])}）" for s in secs]
            prev = st.session_state.get(f"sec_prev_{year}_{ci}")
            val = st.radio("选择小节", options, key=f"sec_{year}_{ci}",
                           label_visibility="collapsed")
            if prev is not None and val != prev:
                st.session_state.cur_sec = (ci, options.index(val))
                st.session_state.cur_sheet = None
                st.session_state.mode = 'sec'
            st.session_state[f"sec_prev_{year}_{ci}"] = val


def render_one(year, sheet, factor, big_title=True):
    data = get_grid(year, sheet)
    if not data:
        st.error(f"未找到表格：{year} / {sheet}")
        return
    meta = (f"{year} 年 · {sheet} · 共 {data['rows']} 行 × {data['cols']} 列"
            + (f" · PDF 第 {data['page'].strip()} 页" if data['page'] else ""))
    if big_title:
        st.markdown(f"### {data['display']}")
        st.caption(meta)
    c1, c2, c3 = st.columns([1, 1, 3])
    with c1:
        compare = st.toggle("跨年对比", key=f"cmp_{year}_{sheet}")
    with c2:
        st.download_button(
            "导出 CSV", data=grid_to_csv(render_grid(data['grid'], factor)),
            file_name=f"{year}_{sheet}.csv", mime="text/csv",
            key=f"dl_{year}_{sheet}")
    with c3:
        if not big_title:
            st.caption(meta)
    if compare:
        pairs = get_compare_list(sheet)
        if len(pairs) <= 1:
            st.info("未找到其他年度的同名表格。")
        for (y, target) in pairs:
            g = get_grid(y, target)
            if not g:
                continue
            st.markdown(f"**{y} 年 · {target}**"
                        + (f" · PDF 第 {g['page'].strip()} 页" if g['page'] else ""))
            st.html(render_table_html(g['grid'], factor))
    else:
        st.html(render_table_html(data['grid'], factor))


def render_section(year, factor, ch, sec):
    """节下 1 表直开；≤40 表横向页签；>40 表下拉。"""
    tables = sec['tables']
    if len(tables) == 1:
        render_one(year, tables[0]['sheet'], factor, big_title=True)
        return
    labels, mapping = [], {}
    for t in tables:
        label = t['display']
        if label in mapping:
            label = f"{label}（{t['sheet']}）"
        mapping[label] = t['sheet']
        labels.append(label)
    if len(tables) <= TAB_LIMIT:
        tabs = st.tabs(labels)
        for tab, t in zip(tabs, tables):
            with tab:
                render_one(year, t['sheet'], factor, big_title=False)
    else:
        val = st.selectbox(f"本节共 {len(labels)} 张表，请选择", labels,
                           key=f"big_{year}_{ch}_{sec['name']}")
        render_one(year, mapping[val], factor, big_title=True)


# ==================== 主区域 ====================
if not tree:
    st.info("数据库中暂无该年度表格。")
    st.stop()

if st.session_state.mode == 'srch' and q.strip() and st.session_state.cur_sheet:
    # 搜索模式：直开单表
    render_one(year, st.session_state.cur_sheet, factor, big_title=True)
else:
    if st.session_state.cur_sec is None:
        st.info("数据库中暂无该年度表格。")
        st.stop()
    ci, si = st.session_state.cur_sec
    ch = tree[ci]
    secs = [s for s in ch['sections'] if s['tables']]
    sec = secs[min(si, len(secs) - 1)]
    st.markdown(f"### {ch['chapter']} · {sec['name']}")
    render_section(year, factor, ch, sec)
