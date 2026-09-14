// 活动映射列表中的一行：状态灯 + URL/命令 + 目标信息 + 操作按钮

import { useState } from 'react'
import { openUrl } from '@tauri-apps/plugin-opener'
import { api, type JumphostInput, type Mapping } from '../ipc'
import { useApp } from '../stores'
import { isWebScheme, localDisplay } from '../lib'

interface Props {
  mapping: Mapping
  jumphost: JumphostInput | null
}

export function MappingRow({ mapping, jumphost }: Props) {
  const { tunnelStatus, mappings, setMappings, addLog } = useApp()
  const [busy, setBusy] = useState(false)

  const status = tunnelStatus[mapping.id] ?? { state: 'stopped' }
  const active = status.state === 'running'
  const port =
    status.state === 'running'
      ? status.actualPort
      : mapping.autoPort
        ? null
        : mapping.localPort || null

  const display = localDisplay(mapping.scheme, port, mapping.username)
  const web = isWebScheme(mapping.scheme)

  const openUrlAction = async () => {
    if (!web) {
      addLog({ ts: Date.now(), level: 'info', msg: '该映射为 tcp 协议，无法用浏览器打开，已改用复制' })
      await copy()
      return
    }
    if (!active) {
      addLog({ ts: Date.now(), level: 'info', msg: '请先启动该映射再打开 URL' })
      return
    }
    await openUrl(display)
    addLog({ ts: Date.now(), level: 'info', msg: `已在浏览器打开：${display}` })
  }

  const copy = async () => {
    if (!active) {
      addLog({ ts: Date.now(), level: 'info', msg: '请先启动该映射再复制' })
      return
    }
    await navigator.clipboard.writeText(display)
    addLog({ ts: Date.now(), level: 'info', msg: `已复制到剪贴板：${display}` })
  }

  const toggle = async () => {
    if (busy) return
    if (!jumphost) return
    setBusy(true)
    if (active) {
      await api.stopTunnel(mapping.id)
    } else {
      try {
        await api.startTunnel(mapping.id, jumphost)
      } catch (e) {
        // 错误状态由 tunnel-status 事件推送
        void e
      }
    }
    setBusy(false)
  }

  const remove = async () => {
    await api.removeMapping(mapping.id)
    setMappings(mappings.filter((m) => m.id !== mapping.id))
    addLog({ ts: Date.now(), level: 'info', msg: '已删除该映射' })
  }

  const dotColor =
    status.state === 'running'
      ? 'bg-success'
      : status.state === 'error'
        ? 'bg-danger'
        : status.state === 'connecting'
          ? 'bg-warning'
          : 'bg-text-dim'

  const toggleLabel =
    status.state === 'connecting'
      ? '连接中…'
      : active
        ? '停止'
        : '启动'

  return (
    <div className="flex items-center rounded-lg bg-surface-2 px-3 py-2">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className={`inline-block h-2.5 w-2.5 rounded-full ${dotColor}`} />
          <button
            className="truncate font-mono text-[12px] text-accent hover:underline"
            onClick={web ? openUrlAction : copy}
            title={web ? '点击在浏览器打开' : '点击复制命令'}
          >
            {display}
          </button>
        </div>
        <div className="mt-0.5 truncate text-[12px] text-dim">
          → {mapping.targetHost}:{mapping.targetPort}
          {mapping.note && <span className="ml-2">| {mapping.note}</span>}
        </div>
      </div>

      <div className="ml-2 flex shrink-0 items-center gap-1.5">
        <button className="btn" onClick={copy}>
          复制
        </button>
        {web && (
          <button className="btn" onClick={openUrlAction}>
            打开
          </button>
        )}
        <button
          className={`btn ${active ? 'btn-warning' : 'btn-success'}`}
          onClick={toggle}
          disabled={busy}
        >
          {toggleLabel}
        </button>
        <button className="btn btn-danger" onClick={remove}>
          删除
        </button>
      </div>
    </div>
  )
}
