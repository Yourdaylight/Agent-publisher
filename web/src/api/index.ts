import axios from 'axios';

const http = axios.create({ baseURL: '/api', timeout: 30000 });

// Request interceptor: attach auth token
http.interceptors.request.use((config) => {
  const token = localStorage.getItem('ap_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor: handle 401 redirect to login
http.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401) {
      // Don't redirect if already on login page or doing login request
      const isLoginRequest = error?.config?.url?.includes('/auth/login');
      if (!isLoginRequest && window.location.pathname !== '/login') {
        localStorage.removeItem('ap_token');
        localStorage.removeItem('ap_user');
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  },
);

// Auth
export const loginByAccessKey = (accessKey: string) => http.post('/auth/login', { access_key: accessKey });
export const loginByEmail = (email: string) => http.post('/auth/login', { email });
// Keep legacy `login` alias for backward compatibility
export const login = loginByAccessKey;
export const verifyToken = () => http.get('/auth/verify');
export const getCurrentUser = () => http.get('/auth/me');

// Helper: save user info after login
export const saveUserInfo = (data: { email: string; is_admin: boolean }) => {
  localStorage.setItem('ap_user', JSON.stringify(data));
};

export const getUserInfo = (): { email: string; is_admin: boolean } | null => {
  const raw = localStorage.getItem('ap_user');
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
};

export const clearAuth = () => {
  localStorage.removeItem('ap_token');
  localStorage.removeItem('ap_user');
};

// Settings
export const getSettings = () => http.get('/settings');
export const updateLLMSettings = (data: any) => http.put('/settings/llm', data);
export const updateImageSettings = (data: any) => http.put('/settings/image', data);
export const updateAccessKey = (currentKey: string, newKey: string) =>
  http.put('/settings/access-key', { current_key: currentKey, new_key: newKey });

// Accounts
export const getAccounts = () => http.get('/accounts');
export const getAccount = (id: number) => http.get(`/accounts/${id}`);
export const createAccount = (data: any) => http.post('/accounts', data);
export const updateAccount = (id: number, data: any) => http.put(`/accounts/${id}`, data);
export const deleteAccount = (id: number) => http.delete(`/accounts/${id}`);
export const getAccountFollowers = (id: number, params?: { begin_date?: string; end_date?: string }) =>
  http.get(`/accounts/${id}/followers`, { params });
export const getAccountArticleStats = (id: number, params?: { begin_date?: string; end_date?: string }) =>
  http.get(`/accounts/${id}/article-stats`, { params });

// Agents
export const getAgents = () => http.get('/agents');
export const getAgent = (id: number) => http.get(`/agents/${id}`);
export const createAgent = (data: any) => http.post('/agents', data);
export const updateAgent = (id: number, data: any) => http.put(`/agents/${id}`, data);
export const generateForAgent = (id: number) => http.post(`/agents/${id}/generate`);

// Articles
export const getArticles = (params?: { agent_id?: number; status?: string }) => http.get('/articles', { params });
export const getArticle = (id: number) => http.get(`/articles/${id}`);
export const updateArticle = (id: number, data: any) => http.put(`/articles/${id}`, data);
export const publishArticle = (id: number, data?: { target_account_ids?: number[] }) =>
  http.post(`/articles/${id}/publish`, data ?? {});
export const syncArticle = (id: number, data?: { target_account_ids?: number[] }) =>
  http.post(`/articles/${id}/sync`, data ?? {});
export const getArticlePublishRecords = (id: number) => http.get(`/articles/${id}/publish-records`);
export const generateVariants = (articleId: number, data: { agent_ids: number[]; style_ids: string[] }) =>
  http.post(`/articles/${articleId}/variants`, data);
export const getArticleVariants = (articleId: number) => http.get(`/articles/${articleId}/variants`);

// Style Presets
export const getStylePresets = () => http.get('/style-presets');
export const createStylePreset = (data: { style_id: string; name: string; description?: string; prompt?: string }) =>
  http.post('/style-presets', data);
export const updateStylePreset = (styleId: string, data: { name?: string; description?: string; prompt?: string }) =>
  http.put(`/style-presets/${styleId}`, data);
export const deleteStylePreset = (styleId: string) => http.delete(`/style-presets/${styleId}`);

// Publish Records
export const getPublishRecords = (params?: { article_id?: number; action?: string; status?: string; limit?: number; offset?: number }) =>
  http.get('/publish-records', { params });
export const getPublishStats = () => http.get('/publish-records/stats');
export const getPublishRecord = (id: number) => http.get(`/publish-records/${id}`);

// Tasks
export const getTasks = (params?: { status?: string }) => http.get('/tasks', { params });
export const getRunningTasks = () => http.get('/tasks', { params: { status: 'running' } });
export const getPendingTasks = () => http.get('/tasks', { params: { status: 'pending' } });
export const getTask = (id: number) => http.get(`/tasks/${id}`);
export const batchRun = (agent_ids?: number[]) => http.post('/tasks/batch', { agent_ids });

// Stats
export const getStats = () => http.get('/stats');

// Candidate Materials
export const getMaterials = (params?: {
  agent_id?: number;
  source_type?: string;
  status?: string;
  tags?: string;
  start_date?: string;
  end_date?: string;
  page?: number;
  page_size?: number;
}) => http.get('/candidate-materials', { params });
export const getMaterial = (id: number) => http.get(`/candidate-materials/${id}`);
export const uploadMaterial = (data: { title: string; content?: string; original_url?: string; tags?: string[] }) =>
  http.post('/candidate-materials/upload', data);
export const updateMaterialTags = (id: number, data: { add_tags?: string[]; remove_tags?: string[] }) =>
  http.patch(`/candidate-materials/${id}/tags`, data);
export const deleteAgent = (id: number) => http.delete(`/agents/${id}`);

// Source mode stats
export const getSourceModeStats = () => http.get('/stats/source-modes');
export const getTagStats = () => http.get('/stats/tags');

// Media
export const getMedia = (params?: {
  tag?: string;
  source_kind?: string;
  article_id?: number;
  account_id?: number;
  upload_status?: string;
  page?: number;
  page_size?: number;
}) => http.get('/media', { params });
export const getMediaDetail = (id: number) => http.get(`/media/${id}`);
export const uploadMedia = (file: File, tags?: string, description?: string) => {
  const formData = new FormData();
  formData.append('file', file);
  const params: Record<string, string> = {};
  if (tags) params.tags = tags;
  if (description) params.description = description;
  return http.post('/media', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    params,
    timeout: 60000,
  });
};
export const deleteMedia = (id: number) => http.delete(`/media/${id}`);

export const uploadMarkdown = (content: string, tags?: string[]) =>
  http.post('/markdown', { content, tags });

// Sources (热点数据源)
export const getSources = (params?: { source_type?: string; is_enabled?: boolean }) =>
  http.get('/sources', { params });
export const getSourceDetail = (id: number) => http.get(`/sources/${id}`);
export const createSource = (data: any) => http.post('/sources', data);
export const updateSource = (id: number, data: any) => http.put(`/sources/${id}`, data);
export const deleteSource = (id: number) => http.delete(`/sources/${id}`);
export const toggleSource = (id: number, is_enabled: boolean) =>
  http.patch(`/sources/${id}/toggle`, { is_enabled });
export const testRssUrl = (url: string) => http.post('/sources/test-rss', { url });
export const bindAgentSource = (agentId: number, data: any) =>
  http.post(`/sources/agents/${agentId}/bindings`, data);
export const unbindAgentSource = (agentId: number, sourceId: number) =>
  http.delete(`/sources/agents/${agentId}/bindings/${sourceId}`);

// LLM Profiles
export const getLLMProfiles = () => http.get('/llm-profiles');

// Extensions
export const getExtensions = () => http.get('/extensions');
export const createLLMProfile = (data: any) => http.post('/llm-profiles', data);
export const updateLLMProfile = (id: number, data: any) => http.put(`/llm-profiles/${id}`, data);
export const deleteLLMProfile = (id: number) => http.delete(`/llm-profiles/${id}`);
export const setDefaultLLMProfile = (id: number) => http.post(`/llm-profiles/${id}/set-default`);
export const getTrendingPlatforms = () => http.get('/sources/trending-platforms');
export const getAgentBindings = (agentId: number) =>
  http.get(`/sources/agents/${agentId}/bindings`);
export const collectForAgent = (agentId: number) =>
  http.post(`/sources/agents/${agentId}/collect`);

// Permission Groups (admin-managed)
export const getGroups = () => http.get('/groups');
export const createGroup = (data: { name: string; description?: string }) => http.post('/groups', data);
export const updateGroup = (id: number, data: { name?: string; description?: string }) => http.put(`/groups/${id}`, data);
export const deleteGroup = (id: number) => http.delete(`/groups/${id}`);
export const addGroupMember = (groupId: number, data: { email: string }) =>
  http.post(`/groups/${groupId}/members`, data);
export const removeGroupMember = (groupId: number, email: string) =>
  http.delete(`/groups/${groupId}/members/${encodeURIComponent(email)}`);

// Slideshow (PPT + Video generation)
export const generateSlideshow = (articleId: number, withTts: boolean = true) =>
  http.post('/extensions/slideshow/generate', { article_id: articleId, with_tts: withTts });

export const getSlideshowStatus = (taskId: number) =>
  http.get(`/extensions/slideshow/status/${taskId}`);

export const getSlideshowPreviewUrl = (taskId: number): string => {
  const token = localStorage.getItem('ap_token') || '';
  return `/api/extensions/slideshow/preview/${taskId}?token=${encodeURIComponent(token)}`;
};

export const downloadSlideshowVideo = (taskId: number): void => {
  const token = localStorage.getItem('ap_token') || '';
  const url = `/api/extensions/slideshow/download/${taskId}?token=${encodeURIComponent(token)}`;
  const a = document.createElement('a');
  a.href = url;
  a.download = '';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
};

export const downloadSlideshowSubtitle = (taskId: number): void => {
  const token = localStorage.getItem('ap_token') || '';
  const url = `/api/extensions/slideshow/subtitle/${taskId}?token=${encodeURIComponent(token)}`;
  const a = document.createElement('a');
  a.href = url;
  a.download = '';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
};

export default http;
