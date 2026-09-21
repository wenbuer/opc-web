function lum(hex){
  const c = hex.replace('#','');
  const rgb = [0,2,4].map(i => parseInt(c.substr(i,2),16)/255)
    .map(v => v <= 0.03928 ? v/12.92 : Math.pow((v+0.055)/1.055, 2.4));
  return 0.2126*rgb[0] + 0.7152*rgb[1] + 0.0722*rgb[2];
}
function ratio(a,b){ const la=lum(a), lb=lum(b); const hi=Math.max(la,lb), lo=Math.min(la,lb); return (hi+0.05)/(lo+0.05); }
const pairs = [
  ['金(现选) 于 卡片',        '#9C6F14', '#FAFBFD'],
  ['金(浅) 于 卡片',          '#B8860B', '#FAFBFD'],
  ['金(深) 于 卡片',          '#8A6420', '#FAFBFD'],
  ['白字 于 金(现选)实底',    '#FFFFFF', '#9C6F14'],
  ['白字 于 金(深)实底',      '#FFFFFF', '#8A6420'],
  ['白字 于 金(浅)实底',      '#FFFFFF', '#B8860B'],
  ['正文字 于 卡片',          '#151A22', '#FAFBFD'],
  ['正文字 于 底色',          '#151A22', '#EDF1F6'],
  ['次级字 于 卡片',          '#5A6472', '#FAFBFD'],
  ['金容器底上的金',          '#9C6F14', '#F7EBCB'],
  ['靛 于 卡片',              '#3E5FA8', '#FAFBFD'],
  ['白字 于 靛实底',          '#FFFFFF', '#3E5FA8'],
  ['红 于 卡片',              '#B3261E', '#FAFBFD'],
  ['白字 于 红实底',          '#FFFFFF', '#B3261E'],
  ['绿 于 卡片',              '#1F7A5A', '#FAFBFD'],
  ['白字 于 绿实底',          '#FFFFFF', '#1F7A5A'],
  ['轮廓线 于 卡片',          '#B4BFCD', '#FAFBFD'],
];
for (const [name, fg, bg] of pairs) {
  const r = ratio(fg, bg);
  const tag = r >= 4.5 ? 'AA正常文本 OK' : (r >= 3 ? '仅大字/图形 OK' : '不足 3:1');
  console.log(name.padEnd(22) + fg + ' on ' + bg + '  = ' + r.toFixed(2) + '  ' + tag);
}
