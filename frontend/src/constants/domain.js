export const roles = Object.freeze({admin: '值班负责人', analyst: '分析员', observer: '观察员'});
export const runLabels = Object.freeze({queued: '待计算', running: '计算中', ready: '待复核', published: '已发布', failed: '计算失败'});
export const stationLabels = Object.freeze({core: '核心站', border: '边界站', noise: '失群', low_sample: '低样本', no_data: '无记录', unreconciled: '未对账'});
export const exceptionNotes = Object.freeze({noise: '核对自助柜日志与登记小时，再决定是否单独排班。', low_sample: '延长采样窗口，归还量达门槛后重新计算。', no_data: '联系站点确认窗口内是否开放、是否漏传。', unreconciled: '先对上柜机流水与纸联：补齐缺失的站点或日期，或核对争议件数，再重新计算。'});
export const channelLabels = Object.freeze({manual: '人工', cabinet: '柜机流水', paper: '纸联'});
export const recordStateLabels = Object.freeze({manual: '人工实收', confirmed: '人工实收', paired: '两路成对', disputed: '件数有争议', standalone: '单边实收', duplicate: '重复登记', ambiguous: '待确认', unmatched: '未对上'});
export const reconStateLabels = Object.freeze({clean: '已对账', partial: '部分对上', unreconciled: '未对账', no_data: '无记录'});
export const demoPeriod = Object.freeze({start: '2026-11-09', end: '2026-11-15'});
