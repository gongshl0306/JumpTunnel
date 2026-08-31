// 主界面：跳板机配置 / 新增映射 / 活动映射 / 日志
// 隧道状态与日志由后端事件驱动。

import { useEffect, useState } from 'react'
import { listen } from '@tauri-apps/api/event'
import { JumphostPanel } from './components/JumphostPanel'
import { MappingForm } from './components/MappingForm'
import { MappingRow } from './components/MappingRow'
import { LogPanel } from './components/LogPanel'
import { api, type JumphostInput, type LogEvent, type TunnelStatusEvent } from './ipc'
import { useApp } from './stores'

export default function App() {
  const { mappings, setTunnelStatus, addLog, initialized, init } = useApp()
  // 跳板机输入提升到 App 层，供「全部启动」与每行启动使用
  const [jump, setJump] = useState<JumphostInput | null>(null)

  useEffect(() => {
    void init()
  }, [init])

  // 订阅后端事件
  useEffect(() => {
    const un1 = listen<TunnelStatusEvent>('tunnel-status', (e) => {
      setTunnelStatus(e.payload.id, e.payload.status)
    })
    const un2 = listen<LogEvent>('log', (e) => {
      addLog(e.payload)
    })
    return () => {
      void un1.then((f) => f())
      void un2.then((f) => f())
    }
  }, [setTunnelStatus, addLog])

  const startAll = async () => {
    if (!jump) {
      alert('请先填写跳板机信息')
      return
    }
    await api.startAll(jump)
  }

  const stopAll = async () => {
    await api.stopAll()
  }

  if (!initialized) {
    return <div className="flex h-full items-center justify-center text-dim">加载中…</div>
  }

  return (
    <div className="flex h-full flex-col gap-3 overflow-y-auto p-3">
      <JumphostPanel onJumphostChange={setJump} />
      <MappingForm />

      <section className="flex min-h-0 flex-1 flex-col rounded-lg bg-surface p-3">
        <div className="mb-2 flex items-center">
          <h2 className="text-[15px] font-bold">活动映射</h2>
          <div className="ml-auto flex gap-1.5">
            <button className="btn btn-success" onClick={startAll}>
              全部启动
            </button>
            <button className="btn btn-warning" onClick={stopAll}>
              全部停止
            </button>
          </div>
        </div>
        <div className="flex flex-1 flex-col gap-2 overflow-y-auto">
          {mappings.length === 0 ? (
            <div className="py-6 text-center text-dim">
              暂无映射，请在上方「新增映射」区添加
            </div>
          ) : (
            mappings.map((m) => (
              <MappingRow key={m.id} mapping={m} jumphost={jump} />
            ))
          )}
        </div>
      </section>

      <LogPanel />
    </div>
  )
}
