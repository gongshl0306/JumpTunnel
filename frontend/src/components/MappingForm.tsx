// 新增映射区：目标 IP/端口/协议 + 本地端口/备注

import { useState } from 'react'
import { api, type Mapping } from '../ipc'
import { useApp } from '../stores'
import { SCHEMES, guessScheme } from '../lib'

export function MappingForm() {
  const { mappings, setMappings, addLog } = useApp()
  const [targetHost, setTargetHost] = useState('')
  const [targetPort, setTargetPort] = useState('')
  const [scheme, setScheme] = useState('http')
  const [username, setUsername] = useState('root')
  const [autoPort, setAutoPort] = useState(true)
  const [localPort, setLocalPort] = useState('')
  const [note, setNote] = useState('')

  const onPortChange = (v: string) => {
    setTargetPort(v)
    const guessed = guessScheme(v)
    if (guessed !== scheme) setScheme(guessed)
  }

  const addMapping = async () => {
    const th = targetHost.trim()
    const tp = targetPort.trim()
    if (!th || !tp) {
      alert('请填写目标 IP 和目标端口')
      return
    }
    const tpNum = parseInt(tp, 10)
    if (Number.isNaN(tpNum)) {
      alert('目标端口必须是整数')
      return
    }
    let localPortNum = 0
    if (!autoPort) {
      const lp = localPort.trim()
      localPortNum = lp ? parseInt(lp, 10) : 0
      if (Number.isNaN(localPortNum)) {
        alert('本地端口必须是整数')
        return
      }
    }

    const mapping: Mapping = {
      id: '',
      autoPort,
      localPort: localPortNum,
      targetHost: th,
      targetPort: tpNum,
      scheme,
      username: scheme === 'ssh' ? username.trim() || 'root' : '',
      note: note.trim(),
    }
    const saved = await api.addMapping(mapping)
    setMappings([...mappings, saved])
    addLog({ ts: Date.now(), level: 'info', msg: `已添加映射：${th}:${tpNum}` })
    // 清空目标输入，方便连续添加
    setTargetHost('')
    setTargetPort('')
    setNote('')
  }

  return (
    <section className="rounded-lg bg-surface p-3">
      <h2 className="mb-2 text-[15px] font-bold">新增映射</h2>

      <div className="mb-2 flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-1">
          <span className="text-dim">目标IP</span>
          <input
            className="input w-36"
            placeholder="如 172.17.12.22"
            value={targetHost}
            onChange={(e) => setTargetHost(e.target.value)}
          />
        </label>
        <label className="flex items-center gap-1">
          <span className="text-dim">目标端口</span>
          <input
            className="input w-16"
            placeholder="443"
            value={targetPort}
            onChange={(e) => onPortChange(e.target.value)}
          />
        </label>
        <label className="flex items-center gap-1">
          <span className="text-dim">协议</span>
          <select
            className="h-8 w-24 rounded-md border border-border bg-surface-2 px-2 text-[13px] outline-none"
            value={scheme}
            onChange={(e) => setScheme(e.target.value)}
          >
            {SCHEMES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        {scheme === 'ssh' && (
          <label className="flex items-center gap-1">
            <span className="text-dim">登录用户</span>
            <input
              className="input w-20"
              placeholder="root"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
          </label>
        )}
        <button className="btn btn-success ml-auto" onClick={addMapping}>
          ＋ 添加映射
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-1">
          <input
            type="checkbox"
            checked={autoPort}
            onChange={(e) => setAutoPort(e.target.checked)}
          />
          自动端口
        </label>
        <label className="flex items-center gap-1">
          <span className="text-dim">本地端口</span>
          <input
            className="input w-20"
            placeholder="留空=自动"
            value={localPort}
            disabled={autoPort}
            onChange={(e) => setLocalPort(e.target.value)}
          />
        </label>
        <label className="flex items-center gap-1">
          <span className="text-dim">备注</span>
          <input
            className="input w-48"
            placeholder="可选"
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
        </label>
      </div>
    </section>
  )
}
