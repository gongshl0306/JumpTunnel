// 与 Rust 后端通信的封装：类型 + invoke 调用。
// 字段名与 Rust serde 的 camelCase 输出保持一致。

import { invoke } from '@tauri-apps/api/core'

// ---------- 类型 ----------

export interface Profile {
  name: string
  host: string
  port: number
  username: string
  password: string
}

export interface Mapping {
  id: string
  autoPort: boolean
  localPort: number
  targetHost: string
  targetPort: number
  scheme: string
  username: string
  note: string
}

export interface Config {
  profiles: Profile[]
  lastMappings: Mapping[]
  lastProfile: string
}

export type TunnelStatus =
  | { state: 'stopped' }
  | { state: 'connecting' }
  | { state: 'running'; actualPort: number }
  | { state: 'error'; message: string }

export interface TunnelStatusPair {
  id: string
  status: TunnelStatus
}

export interface InitialState {
  config: Config
  tunnelStatuses: TunnelStatusPair[]
}

export interface JumphostInput {
  host: string
  port: number
  username: string
  password: string
}

// ---------- 事件 payload 类型 ----------

export interface TunnelStatusEvent {
  id: string
  status: TunnelStatus
}

export interface LogEvent {
  ts: number
  level: string
  msg: string
}

// ---------- 命令 ----------

export const api = {
  getInitialState: () => invoke<InitialState>('get_initial_state'),
  listProfiles: () => invoke<Profile[]>('list_profiles'),
  saveProfile: (profile: Profile) => invoke<void>('save_profile', { profile }),
  deleteProfile: (name: string) => invoke<void>('delete_profile', { name }),
  setLastProfile: (name: string) => invoke<void>('set_last_profile', { name }),
  addMapping: (mapping: Mapping) => invoke<Mapping>('add_mapping', { mapping }),
  updateMapping: (mapping: Mapping) => invoke<void>('update_mapping', { mapping }),
  removeMapping: (id: string) => invoke<void>('remove_mapping', { id }),
  testConnection: (jump: JumphostInput) => invoke<void>('test_connection', { jump }),
  startTunnel: (id: string, jump: JumphostInput) =>
    invoke<number>('start_tunnel', { id, jump }),
  stopTunnel: (id: string) => invoke<void>('stop_tunnel', { id }),
  startAll: (jump: JumphostInput) =>
    invoke<[string, { ok?: number; err?: string }][]>('start_all', { jump }),
  stopAll: () => invoke<void>('stop_all'),
}
