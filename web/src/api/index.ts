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
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  },
);

// Auth
export const login = (accessKey: string) => http.post('/auth/login', { access_key: accessKey });
export const verifyToken = () => http.get('/auth/verify');

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
export const publishArticle = (id: number) => http.post(`/articles/${id}/publish`);
export const syncArticle = (id: number) => http.post(`/articles/${id}/sync`);
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

export default http;
