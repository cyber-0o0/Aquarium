import axios from 'axios';

let API_URL = process.env.NEXT_PUBLIC_API_URL || '/api/v1/';
if (API_URL.startsWith('http') && !API_URL.includes('/api/v1')) {
  API_URL = API_URL.replace(/\/$/, '') + '/api/v1/';
}
if (API_URL === '/api/v1') API_URL = '/api/v1/';

export const apiClient = axios.create({
  baseURL: API_URL,
  headers: { 'Content-Type': 'application/json' },
});

apiClient.interceptors.request.use((config) => {
  const { useAuthStore } = require('@/store/authStore');
  const token = useAuthStore.getState().accessToken;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// ── Auth ──────────────────────────────────────────────────────────────────────

export const authApi = {
  loginWithTelegram: async (initData: string) => {
    const { data } = await apiClient.post('auth/telegram', { init_data: initData });
    return data;
  },
  getNonce: async (): Promise<{ nonce: string; expires_at: string }> => {
    const { data } = await apiClient.get('auth/nonce');
    return data;
  },
  tonConnect: async (walletAddress: string, publicKey: string, signature: string, nonce: string) => {
    const { data } = await apiClient.post('auth/ton-connect', {
      wallet_address: walletAddress,
      public_key: publicKey,
      signature,
      nonce,
    });
    return data;
  },
};

// ── Users ─────────────────────────────────────────────────────────────────────

export const userApi = {
  getMe: async () => {
    const { data } = await apiClient.get('users/me');
    return data;
  },
};

// ── Agents ────────────────────────────────────────────────────────────────────

export const agentApi = {
  getAgents: async () => {
    const { data } = await apiClient.get('agents');
    return data;
  },
  createAgent: async (agentData: any) => {
    const { data } = await apiClient.post('agents', agentData);
    return data;
  },
  getModels: async () => {
    const { data } = await apiClient.get('agents/models');
    return data;
  },
  runAgent: async (id: string, input: string) => {
    const { data } = await apiClient.post(`agents/${id}/run`, { input });
    return data;
  },
  getAgent: async (id: string) => (await apiClient.get(`agents/${id}`)).data,
  updateAgent: async (id: string, data: any) => (await apiClient.patch(`agents/${id}`, data)).data,
  deleteAgent: async (id: string) => (await apiClient.delete(`agents/${id}`)).data,
  getAgentTasks: async (id: string) => (await apiClient.get(`agents/${id}/tasks`)).data,
};

// ── Wallet ────────────────────────────────────────────────────────────────────

export const walletApi = {
  /** Full overview: TON + all jettons + total USD */
  getOverview: async () => {
    const { data } = await apiClient.get('wallet/overview');
    return data;
  },

  /** TON balance only */
  getBalance: async () => {
    const { data } = await apiClient.get('wallet/balance');
    return data;
  },

  /** All jetton/token balances */
  getJettons: async () => {
    const { data } = await apiClient.get('wallet/jettons');
    return data;
  },

  /** Paginated transaction history */
  getTransactions: async (limit = 30, beforeLt?: number) => {
    const params: Record<string, any> = { limit };
    if (beforeLt) params.before_lt = beforeLt;
    const { data } = await apiClient.get('wallet/transactions', { params });
    return data;
  },

  /** Deposit address info + ton:// deep-link */
  getDepositInfo: async () => {
    const { data } = await apiClient.get('wallet/deposit');
    return data;
  },

  /** Current TON/USD price (no auth needed) */
  getTonPrice: async () => {
    const { data } = await apiClient.get('wallet/price');
    return data;
  },

  /** Force cache refresh */
  sync: async () => {
    const { data } = await apiClient.post('wallet/sync');
    return data;
  },

  /** Public address lookup (no auth) */
  getAddressBalance: async (address: string) => {
    const { data } = await apiClient.get(`wallet/address/${address}`);
    return data;
  },
};

// ── Skills ────────────────────────────────────────────────────────────────────

export const skillsApi = {
  list: async (params?: { category?: string; search?: string }) => {
    const { data } = await apiClient.get('skills', { params });
    return data;
  },
  getAgentSkills: async (agentId: string) => {
    const { data } = await apiClient.get(`skills/agent/${agentId}`);
    return data;
  },
  install: async (agentId: string, skillId: string) => {
    const { data } = await apiClient.post('skills/install', { agent_id: agentId, skill_id: skillId });
    return data;
  },
  uninstall: async (agentId: string, skillId: string) => {
    const { data } = await apiClient.delete('skills/uninstall', { data: { agent_id: agentId, skill_id: skillId } });
    return data;
  },
  mcpInspect: async (mcpUrl: string) => {
    const { data } = await apiClient.post('skills/mcp/inspect', { mcp_url: mcpUrl });
    return data;
  },
  mcpInstall: async (payload: { agent_id: string; mcp_url: string; tool_name: string; description: string; input_schema: any }) => {
    const { data } = await apiClient.post('skills/mcp/install', payload);
    return data;
  },
};

// ── API Keys ──────────────────────────────────────────────────────────────────

export const apiKeysApi = {
  list: async () => {
    const { data } = await apiClient.get('api-keys');
    return data;
  },
  add: async (payload: { provider: string; api_key: string; label?: string; base_url?: string }) => {
    const { data } = await apiClient.post('api-keys', payload);
    return data;
  },
  delete: async (keyId: string) => {
    await apiClient.delete(`api-keys/${keyId}`);
  },
  verify: async (keyId: string) => {
    const { data } = await apiClient.post(`api-keys/${keyId}/verify`);
    return data;
  },
};

export const feedApi = {
  getFeed: async () => {
    const response = await apiClient.get<any[]>('feed');
    return response.data;
  },
};
