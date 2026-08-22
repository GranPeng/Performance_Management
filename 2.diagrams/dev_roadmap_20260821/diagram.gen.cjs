// 绩效核算系统 · 前端开发路径图 V02 —— 原生画板节点直出（文字内嵌图形，非文本块叠加）
// 输出格式严格对齐 whiteboard-cli --to openapi 的转换器产出（信封 + 字段集）
// 用法: node diagram.gen.cjs  → 产出 diagram.json（+update --input_format raw 直接可用）
const fs = require('fs');

const CARD_W = 330, GAP = 36, MARGIN = 60;
const PITCH = CARD_W + GAP;
const BAR_Y = 150, BAR_H = 46;
const CARD_Y = 216, CARD_H = 440;
const BOTTOM_Y = CARD_Y + CARD_H + 44; // 700
const BOTTOM_H = 175;
const W = MARGIN * 2 + 5 * CARD_W + 4 * GAP; // 1914
const H = BOTTOM_Y + BOTTOM_H + 40;

let seq = 0;
const nid = (p) => `${p}4:${++seq}`;

function textObj(text, { fontSize = 13, bold = false, color = '#1f2329', align = 'left', valign = 'top' } = {}) {
  return {
    text,
    font_weight: bold ? 'bold' : 'regular',
    font_size: fontSize,
    horizontal_align: align,
    vertical_align: valign,
    line_through: false, underline: false, italic: false, angle: 0,
    text_color: color, text_color_type: 1,
    text_background_color_type: 0,
    theme_text_color_code: -1,
    theme_text_background_color_code: -1,
  };
}

function shape({ x, y, w, h, fill, border, dash, invisible, text, fontSize, bold, color, align, valign }) {
  const n = {
    id: nid('o'), type: 'composite_shape', x, y, width: w, height: h,
    style: invisible
      ? { border_opacity: 0, border_width: 'narrow', border_style: 'solid', fill_opacity: 0 }
      : {
          border_opacity: 100, border_width: 'narrow',
          border_color: border || fill, border_color_type: 1,
          border_style: 'solid',
          fill_opacity: 100, fill_color: fill, fill_color_type: 1,
        },
    composite_shape: { type: 'round_rect' },
    text: textObj(text, { fontSize, bold, color, align, valign }),
  };
  return n;
}

function arrow(fromId, toId, x, y, w) {
  return {
    id: nid('c'), type: 'connector', x, y, width: w, height: 1,
    connector: {
      shape: 'polyline', specified_coordinate: true, caption_auto_direction: false, turning_points: [],
      start: { arrow_style: 'none', attached_object: { id: fromId, position: { x: 1, y: 0.5 }, snap_to: 'right' } },
      end: { arrow_style: 'line_arrow', attached_object: { id: toId, position: { x: 0, y: 0.5 }, snap_to: 'left' } },
      start_object: { id: fromId, position: { x: 1, y: 0.5 }, snap_to: 'right' },
      end_object: { id: toId, position: { x: 0, y: 0.5 }, snap_to: 'left' },
    },
    style: { border_color: '#bbbfc4', border_color_type: 1, border_opacity: 100, border_style: 'solid', border_width: 'narrow' },
  };
}

const phases = [
  {
    name: 'F0 现状（已上线）', bar: '#43A047', fill: '#F1F8F2',
    body:
      '已上线 · P1/P2/P3\n' +
      '· 7 个页面骨架已上线：\n' +
      'Dashboard / Employees /\n' +
      'Projects / Actuals / Batches /\n' +
      'PerformanceResults / Rules\n' +
      '· 结果详情侧滑 + 结果书导出\n' +
      '· Actual 录入 / 手工评分写接口\n' +
      '· 计算 preview / run 已通\n' +
      '（jest 150/150，基线 0 差异）',
  },
  {
    name: 'P0 全栈 MVP', bar: '#1E88E5', fill: '#EAF3FD',
    body:
      '最高优先级 · 测试团队进场\n' +
      '目标：完整核验「写入数据\n' +
      '+ 计算引擎」，沿用表格式界面\n' +
      '· 新期间「指标×员工」骨架生成\n' +
      '· 数据写入全通路：Actual 录入\n' +
      '/ 手工评分 / 修改留痕\n' +
      '· 计算 preview → run → 锁定\n' +
      '· 结果明细 + 结果书导出\n' +
      '· 异常清单页：算不成逐条可见\n' +
      '· 手工校准通道（留痕）\n' +
      '· V05/V60 基线校对视图\n' +
      '· 主数据维护：成员/渠道/规则',
  },
  {
    name: 'P1 拖拽式组织维护', bar: '#8E24AA', fill: '#F7ECFA',
    body:
      '待建 · 依赖 P0 写路径稳定\n' +
      '· 在表格式界面基础上\n' +
      '单开独立入口\n' +
      '· React Flow 节点式拖拽维护\n' +
      '组织 / 岗位 / 人员 / 项目关系\n' +
      '· 生效区间可视化\n' +
      '· 数据层已就绪',
  },
  {
    name: 'P2 评价工作流', bar: '#00897B', fill: '#E9F5F3',
    body:
      '规划 · 借鉴 V3 画板\n' +
      '· 评价任务派发 + 到期催办\n' +
      '（每月 5 日核算死线）\n' +
      '· 量表行为锚点 + 打分证据\n' +
      '（0-60/60-80/80-100 可审计）\n' +
      '· 校准留痕 + 员工申诉\n' +
      '· 依赖 P0 闭环跑通',
  },
  {
    name: 'P3 P5 报数入口', bar: '#546E7A', fill: '#EEF1F3',
    body:
      '规划 · 最后接入\n' +
      '· 飞书 bot 对话报数\n' +
      '→ 结构化 → 写 SQL\n' +
      '· 业务员免登录应用\n' +
      '· 依赖 P0 + 数据通路稳定',
  },
];

const bottomBoxes = [
  {
    title: 'MVP 验收口径（测试团队核验清单）', color: '#1E88E5', w: 610,
    text: '① 数据写入：录入 / 导入 / 修改全通路可用且留痕；② 计算引擎：preview / run / 锁定 / 结果书结果正确；③ 对账：V05 / V60 外部基线 0 差异；④ 异常与手工调整全部留痕可查。',
  },
  {
    title: '协作红线（不变）', color: '#D32F2F', w: 610,
    text: 'QA 只读 · 结果锁定后禁止覆盖重算 · 权威源 = 外部独立标准答案（V05 绩效框架 / V60 预算 Excel），禁止系统自证 · 手工调整必须留痕 · 规则改配置不改公式。',
  },
  {
    title: '备份线（PO 指示：最低优先级）', color: '#546E7A', w: 534,
    text: '本地 CSV 定期导出 cron + 备份 Base（D-024 禁关联表）。开发全部完成后再执行，不占用 P0~P3 资源。',
  },
];

const nodes = [];

// 标题：无填充无边框的图形节点，文字内嵌（单一原生节点）
nodes.push(shape({
  x: MARGIN, y: 26, w: W - MARGIN * 2, h: 44, invisible: true,
  text: '绩效核算系统 · 前端开发路径图', fontSize: 28, bold: true, color: '#1f2329', align: 'center', valign: 'top',
}));
nodes.push(shape({
  x: MARGIN, y: 76, w: W - MARGIN * 2, h: 26, invisible: true,
  text: '2026-08-21 V02 ｜ P0 = 表格式全栈 MVP（测试团队核验写入 + 计算引擎）｜ 拖拽维护降为 P1 独立入口 ｜ 骨架参照 V3 画板',
  fontSize: 14, color: '#5F6368', align: 'center', valign: 'top',
}));

// 图例（色块内嵌文字）
const legend = [
  ['#43A047', '已上线'], ['#1E88E5', '下一步 P0'], ['#8E24AA', '待建 P1'], ['#00897B', '规划 P2'], ['#546E7A', '最后接入 P3'],
];
let lx = MARGIN + 320;
legend.forEach(([c, label]) => {
  nodes.push(shape({
    x: lx, y: 112, w: 150, h: 28, fill: c,
    text: label, fontSize: 13, bold: true, color: '#FFFFFF', align: 'center', valign: 'top',
  }));
  lx += 150 + 24;
});

// 阶段列
const barIds = [];
phases.forEach((p, i) => {
  const x = MARGIN + i * PITCH;
  const bar = shape({
    x, y: BAR_Y, w: CARD_W, h: BAR_H, fill: p.bar,
    text: p.name, fontSize: 16, bold: true, color: '#FFFFFF', align: 'center', valign: 'top',
  });
  barIds.push(bar.id);
  nodes.push(bar);
  nodes.push(shape({
    x, y: CARD_Y, w: CARD_W, h: CARD_H, fill: p.fill, border: p.bar, dash: true,
    text: p.body, fontSize: 13, color: '#3C4043', align: 'left', valign: 'top',
  }));
  if (i > 0) nodes.push(arrow(barIds[i - 1], bar.id, x - GAP, BAR_Y + BAR_H / 2, GAP));
});

// 底部三块
let bx = MARGIN;
bottomBoxes.forEach((b) => {
  nodes.push(shape({
    x: bx, y: BOTTOM_Y, w: b.w, h: BOTTOM_H, fill: '#FFFFFF', border: b.color,
    text: b.title + '\n' + b.text, fontSize: 13, color: '#3C4043', align: 'left', valign: 'top',
  }));
  bx += b.w + 20;
});

const envelope = {
  code: 0,
  data: {
    to: 'openapi',
    result: { nodes },
    metadata: { width: 0, height: 0, nodeCount: nodes.length, connectorCount: nodes.filter(n => n.type === 'connector').length },
  },
  error: '',
};
fs.writeFileSync(__dirname + '/diagram.json', JSON.stringify(envelope, null, 1));
console.log('written', W, 'x', H, 'nodes:', nodes.length);
