// 全局状态：配置、映射、隧道状态、日志。
// 隧道状态与日志由后端事件驱动更新。

import { create } from 'zustand'
import { api, type Config, type Mapping, type TunnelStatus } from './ipc'

export interface LogLine {
  ts: number
  level: string
  msg: string
}

const LOG_MAX_LINES = 400

interface AppState {
  config: Config
  mappings: Mapping[]
  tunnelStatus: Record<string, TunnelStatus>
  logs: LogLine[]
  initialized: boolean

  init: () => Promise<void>
  setConfig: (config: Config) => void
  setMappings: (mappings: Mapping[]) => void
  setTunnelStatus: (id: string, status: TunnelStatus) => void
  addLog: (line: LogLine) => void
}

export const useApp = create<AppState>((set) => ({
  config: { profiles: [], lastMappings: [], lastProfile: '' },
  mappings: [],
  tunnelStatus: {},
  logs: [],
  initialized: false,

  init: async () => {
    const state = await api.getInitialState()
    set({
      config: state.config,
      mappings: state.config.lastMappings,
      tunnelStatus: Object.fromEntries(
        state.tunnelStatuses.map((p) => [p.id, p.status]),
      ),
      initialized: true,
    })
  },

  setConfig: (config) => set({ config }),
  setMappings: (mappings) => set({ mappings }),
  setTunnelStatus: (id, status) =>
    set((s) => ({ tunnelStatus: { ...s.tunnelStatus, [id]: status } })),
  addLog: (line) =>
    set((s) => {
      const logs = [...s.logs, line]
      return { logs: logs.length > LOG_MAX_LINES ? logs.slice(-LOG_MAX_LINES) : logs }
    }),
}))
