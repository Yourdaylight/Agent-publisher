export const formatDateTime = (date?: string | null) => (date ? new Date(date).toLocaleString('zh-CN') : '-');

export const formatShortTime = (date?: string | null) => {
  if (!date) return '-';
  const target = new Date(date).getTime();
  const now = Date.now();
  const diff = Math.max(now - target, 0);
  const hour = 60 * 60 * 1000;
  const day = 24 * hour;
  if (diff < hour) return `${Math.max(1, Math.floor(diff / (60 * 1000)))} 分钟前`;
  if (diff < day) return `${Math.floor(diff / hour)} 小时前`;
  return `${Math.floor(diff / day)} 天前`;
};
