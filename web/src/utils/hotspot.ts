export const getHotspotPlatform = (row: any) => row?.metadata?.platform_name || row?.metadata?.platform || row?.tags?.find((tag: string) => tag.startsWith('platform:'))?.replace('platform:', '') || '未知';

export const qualityBarColor = (score: number | null): string => {
  if (score == null) return 'var(--td-gray-color-5)';
  if (score >= 0.8) return 'var(--td-error-color)';
  if (score >= 0.6) return 'var(--td-warning-color)';
  return 'var(--td-brand-color)';
};

export const heatLabel = (score: number | null): string => {
  if (score == null) return '待评估';
  if (score >= 0.8) return '超热';
  if (score >= 0.6) return '高热';
  return '普通';
};

export const normalizeTag = (tag: string) => tag.startsWith('platform:') ? tag.replace('platform:', '') : tag;
